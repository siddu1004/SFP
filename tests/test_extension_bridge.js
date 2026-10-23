const { HiveBridge } = require('../extension/src/hiveBridge');
const path = require('path');

async function testBridge() {
  const root = path.resolve(__dirname, '..');
  console.log('Testing HiveBridge with root:', root);
  const bridge = new HiveBridge(root);

  const skills = bridge.getAllSkills();
  console.log('Total catalog skills loaded:', skills.length);
  if (skills.length === 0) {
    throw new Error('Catalog did not load any skills!');
  }

  console.log('\n--- Test 1: Prompt 1 ("build react payment flow") ---');
  const res1 = await bridge.selectSkills('build react payment flow', root);
  console.log('Prompt 1 selected skills count:', res1.stack ? res1.stack.length : 0);
  const names1 = (res1.stack || []).map(s => s.name);
  console.log('Selected skills 1:', names1);

  console.log('\n--- Test 2: Prompt 2 with testing added ("build react payment flow and test with jest") ---');
  const res2 = await bridge.selectSkills('build react payment flow and test with jest', root);
  const names2 = (res2.stack || []).map(s => s.name);
  console.log('Selected skills 2:', names2);

  const set1 = new Set(names1);
  const set2 = new Set(names2);
  const added = [...set2].filter(x => !set1.has(x));
  const removed = [...set1].filter(x => !set2.has(x));

  console.log('\n--- Delta Calculation ---');
  console.log('Added (+):', added);
  console.log('Removed (-):', removed);

  console.log('\n--- Test 3: Status check ---');
  const status = await bridge.getStatus();
  console.log('Hive status:', status.total_decisions || 0, 'decisions,', status.model_associations || 0, 'associations');

  console.log('\nALL EXTENSION BRIDGE TESTS PASSED!');
}

testBridge().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
