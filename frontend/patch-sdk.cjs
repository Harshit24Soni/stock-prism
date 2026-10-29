const fs = require('fs');
const path = require('path');

const targetFile = path.join(__dirname, 'node_modules', '@thesysai', 'genui-sdk', 'dist', 'index.js');

if (fs.existsSync(targetFile)) {
  let content = fs.readFileSync(targetFile, 'utf8');
  const target = 'children:[t.map((l,c)=>a(K,{...l,overridesProps:Rd},c)),a(Dd,{})]';
  const replacement = 'children:[Array.isArray(t)?t.map((l,c)=>a(K,{...l,overridesProps:Rd},c)):t,a(Dd,{})]';

  if (content.includes(target)) {
    content = content.replace(target, replacement);
    fs.writeFileSync(targetFile, content, 'utf8');
    console.log('Successfully patched @thesysai/genui-sdk Card component for CustomMarkdown rendering.');
  } else if (content.includes(replacement)) {
    console.log('@thesysai/genui-sdk is already patched.');
  } else {
    console.warn('Could not locate Card children mapping target in @thesysai/genui-sdk.');
  }
} else {
  console.log('SDK not installed yet, skipping patch.');
}

