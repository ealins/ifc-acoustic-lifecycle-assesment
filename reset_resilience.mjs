import { DatabaseSync } from 'node:sqlite';

const dbPath = 'C:/Users/ealin/.omniroute/storage.sqlite';
const db = new DatabaseSync(dbPath);

console.log('Clearing domain_lockout_state...');
db.prepare('DELETE FROM domain_lockout_state').run();

console.log('Clearing connection_runtime_state...');
try {
  db.prepare('DELETE FROM connection_runtime_state').run();
} catch (e) {
  console.log('connection_runtime_state table might not exist:', e.message);
}

console.log('Clearing provider_quota_state...');
try {
  db.prepare('DELETE FROM provider_quota_state').run();
} catch (e) {
  console.log('provider_quota_state table might not exist:', e.message);
}

db.close();
console.log('Resilience states successfully wiped clean!');
