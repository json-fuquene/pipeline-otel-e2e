// Carga constante para el laboratorio observable (ID-003).
// Mantiene tráfico de línea base para el modelo de anomalías y durante los experimentos de caos.
//
//   k6 run -e ORDERS_URL=http://IP:8002 -e CATALOG_URL=http://IP:8001 \
//          -e RATE=5 -e DURATION=3h scripts/load/steady.js
//
// Mezcla por iteración: 70 % POST /orders (orders → catalog → data-service → RDS),
// 20 % GET /orders/summary (orders → data-service, consulta analítica) y 10 % GET /orders.
import http from 'k6/http';
import { check } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const ORDERS = (__ENV.ORDERS_URL || 'http://127.0.0.1:8002').replace(/\/$/, '');
const CATALOG = (__ENV.CATALOG_URL || 'http://127.0.0.1:8001').replace(/\/$/, '');
const RATE = Number(__ENV.RATE || 5);
const DURATION = __ENV.DURATION || '30m';

export const options = {
  discardResponseBodies: false,
  scenarios: {
    steady: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: Math.max(10, RATE * 4),
      maxVUs: Math.max(50, RATE * 20),
    },
  },
  summaryTrendStats: ['avg', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export function setup() {
  const products = [];
  for (let i = 0; i < 5; i += 1) {
    const response = http.post(
      `${CATALOG}/products`,
      JSON.stringify({ name: `Producto carga ${i + 1}`, price: `${(10 + i * 7.5).toFixed(2)}` }),
      { headers: JSON_HEADERS, tags: { name: 'POST /products (setup)' } },
    );
    check(response, { 'producto creado': (r) => r.status === 201 });
    if (response.status === 201) {
      products.push(response.json('id'));
    }
  }
  if (products.length === 0) {
    throw new Error('No se pudo crear ningún producto en catálogo.');
  }
  return { products };
}

export default function (data) {
  const headers = { ...JSON_HEADERS, 'X-Request-ID': uuidv4() };
  const pick = Math.random();
  if (pick < 0.7) {
    const productId = data.products[Math.floor(Math.random() * data.products.length)];
    const response = http.post(
      `${ORDERS}/orders`,
      JSON.stringify({ product_id: productId, quantity: 1 + Math.floor(Math.random() * 3) }),
      { headers, tags: { name: 'POST /orders' } },
    );
    check(response, { 'pedido 201': (r) => r.status === 201 });
  } else if (pick < 0.9) {
    const response = http.get(`${ORDERS}/orders/summary?window_minutes=60`, {
      headers, tags: { name: 'GET /orders/summary' },
    });
    check(response, { 'resumen 200': (r) => r.status === 200 });
  } else {
    const response = http.get(`${ORDERS}/orders?limit=5`, { headers, tags: { name: 'GET /orders' } });
    check(response, { 'listado 200': (r) => r.status === 200 });
  }
}
