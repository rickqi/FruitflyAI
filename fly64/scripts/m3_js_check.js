// JS syntax check via node (module parse)
const fs = require('fs');
const src = fs.readFileSync('web/dashboard.js', 'utf8').replace(/^export\s+/mg, '');
try { new Function(src); console.log('JS_PARSE_OK'); } catch (e) { console.error('JS_PARSE_FAIL', e.message); process.exit(1); }
