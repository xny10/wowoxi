const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(require('node:path').join(__dirname, '../lite/load_more.js'), 'utf8');
function check(options, expected) {
  let clicks = 0;
  const el = {
    innerText: options.label || 'See more', tagName: options.tag || 'BUTTON',
    disabled: options.disabled || false, parentElement: null,
    closest: () => options.article ? {} : null,
    getAttribute: name => name === 'href' ? options.href : null,
    getBoundingClientRect: () => ({left:0, top:850, bottom:910, height:60, width:options.width || 1500}),
    contains: () => false, click: () => clicks++
  };
  const document = {documentElement:{clientWidth:1600}, querySelectorAll:()=>[el], elementFromPoint:()=>options.overlay ? {} : el};
  const fn = vm.runInNewContext(code, {document, innerHeight:1000, getComputedStyle:()=>({})});
  assert.equal(fn(), expected);
  assert.equal(clicks, expected ? 1 : 0);
}
check({}, true);
check({label:'Lihat lainnya'}, true);
check({width:90}, false);
check({article:true}, false);
check({disabled:true}, false);
check({overlay:true}, false);
check({tag:'A',href:'https://shop.example'}, false);
check({label:'Shop now'}, false);
console.log('8 footer selection cases passed');
