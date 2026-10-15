import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const rate = Number(__ENV.RATE || 10);
const warmupSeconds = Number(__ENV.WARMUP_SECONDS || 30);
const durationSeconds = Number(__ENV.DURATION_SECONDS || 180);
const catalogDuration = new Trend('catalog_duration', true);
const ordersDuration = new Trend('orders_duration', true);

export const options = {
  scenarios: {
    constant_load: {
      executor: 'constant-arrival-rate',
      rate,
      timeUnit: '1s',
      duration: `${warmupSeconds + durationSeconds}s`,
      preAllocatedVUs: Math.max(rate, 10),
      maxVUs: Math.max(rate * 4, 40),
    },
  },
  thresholds: {
    checks: ['rate>0.99'],
    dropped_iterations: ['count<1'],
    http_req_failed: ['rate<0.01'],
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export function setup() {
  return {
    catalogUrl: __ENV.BASE_URL_CATALOG,
    ordersUrl: __ENV.BASE_URL_ORDERS,
    productId: __ENV.PRODUCT_ID,
    orderId: __ENV.ORDER_ID,
    measureStart: Date.now() + warmupSeconds * 1000,
  };
}

export default function (data) {
  const product = http.get(`${data.catalogUrl}/products/${data.productId}`, {
    timeout: '5s',
    tags: { service: 'catalog', route: 'GET /products/{product_id}' },
  });
  check(product, { 'catalog returns 200': (response) => response.status === 200 });
  if (Date.now() >= data.measureStart) {
    catalogDuration.add(product.timings.duration);
  }

  const order = http.get(`${data.ordersUrl}/orders/${data.orderId}`, {
    timeout: '5s',
    tags: { service: 'orders', route: 'GET /orders/{order_id}' },
  });
  check(order, { 'orders returns 200': (response) => response.status === 200 });
  if (Date.now() >= data.measureStart) {
    ordersDuration.add(order.timings.duration);
  }
}
