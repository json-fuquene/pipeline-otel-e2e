import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / "docker/chaos/supervisor.py"
SPEC = importlib.util.spec_from_file_location("chaos_supervisor", PATH)
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


class FakeKernel:
    def __init__(self):
        self.active = False
        self.foreign = False
        self.fail_install = False
        self.fail_cleanup = False
        self.removals = 0
        self.route_device = "eth7"

    def route(self, address):
        return self.route_device

    def snapshot(self, device):
        return {"qdisc": [{"handle": "7a10:", "kind": "prio", "root": True},
                          {"handle": "7a20:", "kind": "netem"}] if self.active else [],
                "filters": [{"kind": "u32"}] if self.active else []}

    def preflight(self, address):
        if self.foreign:
            raise supervisor.SafetyError("foreign rules")
        return self.route_device, self.snapshot(self.route_device)

    def root(self, device):
        self.active = True

    def delay(self, device, address):
        if self.fail_install:
            raise supervisor.SafetyError("partial install")

    def remove(self, device):
        if self.fail_cleanup:
            raise supervisor.SafetyError("cleanup failed")
        self.active = False
        self.removals += 1
        return self.snapshot(device)


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.target = "172.22.0.3"
        self.kernel = FakeKernel()
        self.events = []
        self.watchdog = supervisor.Supervisor(self.kernel, lambda: self.now, lambda: self.target, self.events.append)

    def arm(self):
        return self.watchdog.arm("172.22.0.3")

    def test_watchdog_is_armed_before_any_installation(self):
        original = self.kernel.root

        def root(device):
            self.assertEqual(self.watchdog.deadline, 60)
            self.assertEqual(self.events[-1]["event"], "watchdog_armed")
            original(device)

        self.kernel.root = root
        self.assertEqual(self.arm()["state"], "active")

    def test_expired_lease_cleans_without_runner(self):
        self.arm()
        self.now = 10
        self.watchdog.check()
        self.assertEqual(self.watchdog.state, "clean")
        self.assertEqual(self.watchdog.reason, "lease_expired")
        self.assertFalse(self.kernel.active)

    def test_renewal_does_not_extend_ttl(self):
        self.arm()
        for self.now in range(1, 60):
            self.watchdog.renew()
        self.now = 60
        self.watchdog.check()
        self.assertEqual(self.watchdog.reason, "ttl_expired")

    def test_expired_lease_cannot_be_revived(self):
        self.arm()
        self.now = 10
        with self.assertRaises(supervisor.SafetyError):
            self.watchdog.renew()
        self.assertFalse(self.kernel.active)

    def test_partial_installation_cleans_root(self):
        self.kernel.fail_install = True
        with self.assertRaises(supervisor.SafetyError):
            self.arm()
        self.assertEqual(self.watchdog.state, "clean")
        self.assertFalse(self.kernel.active)

    def test_cleanup_failure_is_visible_and_retryable(self):
        self.arm()
        self.kernel.fail_cleanup = True
        with self.assertRaises(supervisor.SafetyError):
            self.watchdog.rollback()
        self.assertEqual(self.watchdog.state, "cleanup_failed")
        self.kernel.fail_cleanup = False
        self.assertEqual(self.watchdog.rollback()["state"], "clean")

    def test_foreign_rules_never_inject(self):
        self.kernel.foreign = True
        with self.assertRaises(supervisor.SafetyError):
            self.arm()
        self.assertFalse(self.kernel.active)
        self.assertFalse(self.watchdog.used)

    def test_target_change_before_arm_is_rejected(self):
        with self.assertRaises(supervisor.SafetyError):
            self.watchdog.arm("172.22.0.4")
        self.assertFalse(self.kernel.active)

    def test_target_change_during_injection_rolls_back(self):
        self.arm()
        self.target = "172.22.0.4"
        self.watchdog.check()
        self.assertEqual(self.watchdog.reason, "target_changed")

    def test_route_change_rolls_back(self):
        self.arm()
        self.kernel.route_device = "eth8"
        self.watchdog.check()
        self.assertFalse(self.kernel.active)

    def test_only_one_injection_allowed(self):
        self.arm()
        self.watchdog.rollback()
        with self.assertRaises(supervisor.SafetyError):
            self.arm()

    def test_repeated_rollback_is_safe(self):
        self.arm()
        self.watchdog.rollback()
        self.assertEqual(self.watchdog.rollback()["state"], "clean")
        self.assertFalse(self.kernel.active)

    def test_idle_rollback_does_not_mutate_kernel(self):
        self.assertEqual(self.watchdog.rollback()["state"], "idle")
        self.assertEqual(self.kernel.removals, 0)

    def test_missing_active_rules_are_not_reported_as_active(self):
        self.arm()
        self.kernel.active = False
        with self.assertRaises(supervisor.SafetyError):
            self.watchdog.status()
        self.assertEqual(self.watchdog.reason, "rules_missing")
        self.assertEqual(self.watchdog.state, "clean")


class KernelTests(unittest.TestCase):
    def test_filter_selects_only_catalog_tcp_and_port(self):
        calls = []
        kernel = supervisor.Kernel(lambda args: calls.append(args) or "[]")
        kernel.root("eth7")
        kernel.delay("eth7", "172.22.0.3")
        root, delay, match = calls
        self.assertEqual(root[-16:], ["0"] * 16)
        self.assertIn("6000ms", delay)
        self.assertIn("172.22.0.3/32", match)
        self.assertIn("8000", match)
        self.assertIn("6", match)
        self.assertIn("nofrag", match)
        self.assertNotIn("replace", sum(calls, []))

    def test_nondefault_qdisc_is_rejected(self):
        def command(args):
            if args[0] == "ip":
                return '[{"dev":"eth7"}]'
            if "qdisc" in args:
                return '[{"kind":"fq_codel","handle":"0:"}]'
            return "[]"

        with self.assertRaises(supervisor.SafetyError):
            supervisor.Kernel(command).preflight("172.22.0.3")

    def test_existing_ingress_rules_are_rejected(self):
        def command(args):
            if args[0] == "ip":
                return '[{"dev":"eth7"}]'
            return '[{"kind":"clsact","handle":"ffff:"}]' if "qdisc" in args else "[]"

        with self.assertRaises(supervisor.SafetyError):
            supervisor.Kernel(command).preflight("172.22.0.3")

    def test_cleanup_leaves_foreign_root_untouched(self):
        calls = []

        def command(args):
            calls.append(args)
            return '[{"kind":"prio","handle":"1234:","root":true}]' if "qdisc" in args else "[]"

        supervisor.Kernel(command).remove("eth7")
        self.assertFalse(any("del" in args for args in calls))

    def test_loopback_route_rejected(self):
        with self.assertRaises(supervisor.SafetyError):
            supervisor.Kernel(lambda args: '[{"dev":"lo"}]').route("127.0.0.1")

    def test_stale_dns_cannot_block_watchdog(self):
        monitor = supervisor.TargetMonitor()
        with self.assertRaises(supervisor.SafetyError):
            monitor.resolve()

    def test_ipv6_or_ambiguous_dns_rejected(self):
        from unittest.mock import patch
        ipv4 = (supervisor.socket.AF_INET, 1, 6, "", ("172.22.0.3", 8000))
        ipv6 = (supervisor.socket.AF_INET6, 1, 6, "", ("::1", 8000, 0, 0))
        for rows in ([ipv4, ipv6], [ipv4, (supervisor.socket.AF_INET, 1, 6, "", ("172.22.0.4", 8000))]):
            with patch.object(supervisor.socket, "getaddrinfo", return_value=rows):
                with self.assertRaises(supervisor.SafetyError):
                    supervisor.target_address()


if __name__ == "__main__":
    unittest.main()
