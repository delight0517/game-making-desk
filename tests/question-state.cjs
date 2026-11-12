const fs = require('fs'), vm = require('vm'), assert = require('assert');
const path = require('path');
const storage = new Map();
let state = {revision: 1, items: {b: {text: 'Preserved answer', status: 'submitted'}}};
const context = {
  window: {addEventListener() {}}, Date,
  localStorage: {getItem: k => storage.get(k) || null, setItem: (k, v) => storage.set(k, v)},
  setTimeout() { return 1; }, clearTimeout() {}, setInterval() {},
  fetch: async (url, options) => {
    if (!options) return {ok: true, json: async () => ({answers: state})};
    const data = JSON.parse(options.body);
    assert.equal(data.questionId, 'internal-question-lifecycle');
    assert.equal(data.revision, state.revision);
    state = {...state, revision: state.revision + 1,
      items: {...state.items, [data.questionId]: {text: data.text, status: 'draft'}}};
    return {ok: true, status: 200, json: async () => state};
  }
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../desk/desk.js'), 'utf8'), context);
(async () => {
  const d = context.desk();
  d.brief = {questions: [{id: 'a', title: 'A'}, {id: 'b', title: 'B'}]};
  d.currentId = 'a'; d.q = d.brief.questions[0]; d.state = state;
  assert.equal(d.questionStatus(d.q), '미확인 · 미응답');
  d.markQuestionSeen('a');
  assert.equal(d.questionStatus(d.q), '미응답');
  d.text = '   ';
  assert(d.questionNeedsAnswer(d.q));
  assert.equal(d.questionStatus(d.brief.questions[1]), '답변 전달됨');
  d.roundMode = true; d.roundDrafts.b = '';
  assert(d.questionNeedsAnswer(d.brief.questions[1]), 'Blank local edit must not fall back to old text');
  d.roundMode = false;
  await d.setQuestionDeleted('b', true);
  assert(d.isQuestionDeleted('b'));
  assert.equal(d.bookQuestions().length, 1);
  assert.equal(state.items.b.text, 'Preserved answer');
  assert.equal(d.currentId, 'a');
  const reopened = context.desk();
  reopened.loadQuestionLifecycle(state);
  assert(reopened.isQuestionDeleted('b'), 'Trash must survive reload');
  await d.setQuestionDeleted('b', false);
  assert(!d.isQuestionDeleted('b'));
  assert.equal(state.items.b.text, 'Preserved answer');
  assert.equal(d.bookQuestions().length, 2);
  console.log('PASS unread/blank/submitted states, durable trash/restore, original answers preserved, no navigation');
})().catch(error => { console.error(error); process.exitCode = 1; });
