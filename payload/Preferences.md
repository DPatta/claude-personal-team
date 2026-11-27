# User preferences (all projects)

Project-level memory or CLAUDE.md may override a rule here for that project only.

## Communication
- **ตอบเป็นภาษาไทยเสมอ** — คำอธิบาย สรุปงาน คำถาม และ progress note สั้น ๆ ระหว่างทำงานด้วย แม้ context ก่อนหน้าจะเป็นอังกฤษ. Technical terms, ชื่อ symbol, path, คำสั่ง และ error message จาก tool ใช้อังกฤษได้.
- **ทุกอย่างที่เข้า git เป็นภาษาอังกฤษ** — commit message, PR title/description, docs ที่อยู่ใน repo. ก่อน commit เช็คว่า message และไฟล์ .md ที่ stage ไม่มีอักษรไทย. มีแค่ chat กับ user ที่เป็นไทย.
- **สอนแบบ concept ก่อน** — เมื่อ user เรียนเรื่องใหม่ (เช่น backend): problem it solves → mental model → how it works under the hood → minimal code → trade-offs/failure modes → check-your-understanding. เชื่อมกับสิ่งที่ user รู้แล้ว (Flutter clean architecture/BLoC, Next.js/TS และ codebase ที่ทำงานอยู่). เริ่มสอนเลย ไม่ต้องถามคำถาม setup หลายข้อก่อน.
- **AskUserQuestion เป็นภาษาไทยทุกช่อง** — question, header, option label และ description; ชื่อ symbol/path ใช้อังกฤษได้. ทวนข้อความก่อนเรียก tool เพราะตัวอย่างใน schema เป็นอังกฤษจึงหลุดง่าย.

## ก่อนถาม / ก่อนลงมือ
- **ก่อนให้ user เลือก** — (a) ถ้าคำถามพึ่งศัพท์ dev (เช่น fixture) อธิบายเป็นไทยก่อนว่าคืออะไร ใช้ทำอะไร และใคร (end user หรือ developer) ต้องใช้; (b) ถ้าตัดสินตามต้นทุน/ความเสี่ยง (conflict, refactor, lint) วัดจริงก่อนแบบไม่แตะของจริง (`git merge-tree --write-tree`, dry run, scratch copy) แล้วใส่ตัวเลขในคำถาม; (c) user ตอบสั้น ๆ เช่น "เปิดเท่าที่จำเป็น" หลังฉันเสนอชุดที่แนะนำ = อนุมัติทั้งชุดที่แนะนำ ถ้าอยากตัดเพิ่มให้ถามก่อน.
- **ขอ plan / ดูผลกระทบ / คำตอบกำกวม ≠ สั่งลงมือ** — "วางแผน", "ดูเรื่องกระทบก่อน", "สร้าง worktree ไว้ก่อนแล้วมาคุยกัน", "ไม่ต้องสนใจ" ไม่ใช่ go. หลัง plan ให้ถามหนึ่งคำถามชัด ๆ ("เริ่มลงมือเลยไหม") ก่อน dispatch หรือแก้โค้ด; ถ้าคำตอบกำกวมให้ถาม อย่าเลือกความหมายที่ลงมือมากที่สุด.
- **user ปฏิเสธ tool call หรือสั่งหยุด → หยุดทันที** — ห้ามลอง tool call ที่เทียบเท่าซ้ำ (รวมที่ค้างจาก wakeup/prompt เก่า). เช่น user บอก "เดี๋ยวรันเอง" = ปล่อยให้ user คุม simulator/app เอง.

## Git
- **Commit ได้เฉพาะเมื่อ user สั่ง** — ห้าม commit เองเมื่องานเสร็จ ให้แจ้งว่าพร้อม commit แล้วรอคำสั่ง. merge commit / ปิด conflict ก็นับเป็น commit. ข้อยกเว้นเดียว: การสั่ง autopilot = สั่ง commit บน local branch `autopilot/*` ของ run นั้น (ยังห้าม push).
- **รูปแบบ commit message (project ส่วนตัว, autopilot และ repo ตั้งค่า Claude เช่น claude-personal-team)** — subject เป็น `<type>: <emoji> <short lowercase subject>` ภาษาอังกฤษ ไม่มีจุดท้าย. emoji ตาม type: feat 🎸, fix 🐛, docs ✏️, style 💄, refactor 💡, perf ⚡️, test 💍, chore 🤖, ci 🎡, release 🏹 (เช่น `fix: 🐛 stop the process tree on close`). ตามด้วย body ภาษาอังกฤษสั้น ๆ (ใส่ task/decision id ถ้ามี) แล้วปิดด้วย `Co-Authored-By`. commit ที่ push ไปแล้วไม่แก้ย้อนหลัง. repo งานที่มีทีมดูแลอยู่แล้วใช้กฎของทีมนั้นแทน. รูปแบบนี้เป็นความชอบส่วนตัว ถ้าอยากใช้แบบอื่นแก้ที่ข้อนี้ได้เลย ที่อื่นอ้างถึงข้อนี้ทั้งหมด.
- **worktree-write-guard บล็อก Write/Edit** → ใช้ `EnterWorktree` เข้า worktree นั้นแล้วแก้ ห้ามหลบด้วย Bash/python และไม่ต้องให้ user รัน script.
- **`.env` ใน worktree ใหม่** — `cp` จาก main checkout ได้ แต่ห้ามเปิดอ่าน/cat/แสดงเนื้อหา.
- **ห้าม `git push` และห้ามเปิด PR (`gh pr create`) เอง** — ทำงานแค่ใน local branch แล้วถามก่อนทุกครั้ง. การอนุญาตครั้งหนึ่งไม่ครอบคลุม push/PR ถัดไป. คำว่า "ทำ PR" / "ทำ PR 1" ของ user = แผนงานก้อนหนึ่ง ไม่ใช่การอนุญาตให้เปิด PR บน GitHub.
- **"merge X เข้า Y" ทำตามตัวอักษร** — checkout Y (ใช้ worktree ถ้า Y ไม่ได้ checkout อยู่) แล้ว `git merge X`. ถ้าคิดว่าอีกทิศดีกว่า ถามหนึ่งบรรทัดก่อน ห้ามสลับทิศเอง (ผล tree เหมือนกันทั้งสองทิศ: `git write-tree` ก่อน `--abort` เพื่อเอาไปใช้ทิศที่ถูกได้).
- **เช็ค branch ก่อน implement** — รัน `git branch --show-current` ให้ตรงกับ branch ของ feature. ถ้าไม่ตรง หยุดแล้วแจ้ง user; อย่าสลับ branch หรือแตะ uncommitted changes เอง. ถ้าเขียน design doc ที่ผูกกับ branch ให้ใส่ section "Branch" ไว้ด้านบน.

## Verification
- **อย่าเชื่อ stdout ที่ผ่าน rtk hook แล้ว pipe ต่อ** — rtk rewrite `git …` เป็น `rtk git …` ซึ่ง filter/ย่อ output: pipe ไป `grep` ได้ 0 hit ทั้งที่มีของ และ redirect ลงไฟล์ได้เนื้อผิด. เช็คว่าโค้ดอยู่บน branch ไหนใช้ `git grep -n "<pattern>" <branch> -- <path>` ไม่ใช่ `git show <branch>:<file> | grep`.
- **Verify handoff ของ subagent ทุกครั้ง** — "แก้เสร็จแล้ว" เชื่อไม่ได้; `grep`/`git diff` ที่ไฟล์จริงก่อนส่งต่อ reviewer/QA. ถ้าเลขบรรทัดที่ agent รายงานไม่ตรงไฟล์จริง แปลว่าอ่าน snapshot เก่าหรือคนละไฟล์ (เช่น worktree ซ้อนใน repo หลัก) — ตรวจ path ทันที.
- **ก่อนสรุปว่า "ไม่มี/ไม่ได้ใช้ใน codebase"** ให้ grep concept นั้นหลายรูปแบบการเขียน (เช่น l10n: `AppLocalizations.of`, `context.l10n`, `l10n.`, `S.of(context)`, `.tr()`, extension, DI accessor) ไม่ใช่แค่รูปแบบเดียวที่นึกออก.

## Safety
- **ห้าม test/probe/mutant ส่ง signal จริง** (`process.kill`, `pkill`, `killall`) ไปที่ pid อื่นนอกจาก pid ที่ test เริ่มเอง — ต้องผ่านตัวส่งที่ allowlist เฉพาะ pid นั้น. ห้าม mutate โค้ด signal/sweep แล้วรัน test ที่ใช้ process จริง. ถ้า permission ปฏิเสธงาน signal ให้หยุดถาม ห้ามหาทางอื่น.
- **UAT / environment ที่ใช้ร่วมกัน: ลบได้เฉพาะ record ที่สร้างเองใน session นั้น** — ทดสอบการลบโดยสร้าง record ชื่อชัด ๆ ก่อนแล้วลบตัวนั้น ห้ามลบของที่มีอยู่ก่อนแม้ดูเหมือน test data; รายงานว่าสร้าง/ลบอะไร.

## Code style
- **ห้ามตั้งชื่อย่อ** — ตัวแปร ฟังก์ชัน parameter ใช้ชื่อเต็มที่สื่อความหมาย แม้จะยาว: `viewModel` ไม่ใช่ `vm`, `batchSettings` ไม่ใช่ `cfg`, `currentLanguage` ไม่ใช่ `lng`.

## Browser automation
- **ใช้ Claude in Chrome (`mcp__claude-in-chrome__*`) เท่านั้น — ห้ามใช้ Playwright** — งานที่ต้องเปิด/คลิก/กรอกฟอร์ม/screenshot/อ่าน console/ตรวจหน้าเว็บ ใช้ Claude in Chrome ทุกครั้ง (โหลด skill `anthropic-skills:chrome-browser` ก่อนใช้ครั้งแรก). ห้ามเรียก `mcp__plugin_ecc_playwright__*`, ห้ามเขียน/รัน Playwright script เพื่อ drive browser, และห้าม dispatch subagent ที่ใช้ Playwright (เช่น `ecc:e2e-runner`, `ecc:gan-evaluator`) แทน. ถ้า Chrome extension ไม่ตอบหรือ error 2–3 ครั้ง ให้หยุดถาม user — อย่า fallback ไป Playwright. ข้อยกเว้นระดับ global: user สั่งรัน Playwright test suite ที่มีอยู่แล้วใน repo เองโดยตรง. ข้อยกเว้นระดับ repo (เช่น `playwright-script-test`, QA session ที่รัน test id ของ repo นั้น) ต้องเขียนไว้ใน memory/CLAUDE.md ของ repo นั้นเท่านั้น และไม่ขยายไป repo อื่น.

## UI / design work
- **"ขอดูก่อน" / "ขอ wireframe" / "confirm ก่อน" = หยุดรอ** — แสดง mockup/wireframe แล้วถามผ่าน AskUserQuestion รอคำตอบก่อน implement ไม่มีข้อยกเว้น.
- **Feedback ที่ชี้ element เดียว ให้แก้แค่ element นั้น** — ทวนชื่อ element (ใช้คำบนจอ) เป็นประโยคไทยสั้น ๆ ก่อนลงมือ และยืนยันว่าส่วนอื่นคงเดิม. ห้ามขยายเป็น "แก้ทุกหน้าให้ consistent" เว้นแต่ user ขอ. เก็บสำเนา mockup เดิมไว้ก่อนเริ่ม design workflow เพื่อ rollback ได้.
- **User ตอบด้วยรูปแทน label ของตัวเลือก** — screenshot อาจหมายถึงทั้ง "หน้าตาที่ต้องการ" หรือ "ฝั่งที่ต้องเปลี่ยน". ทวนทิศทางก่อน: "แปลว่าจะให้ [A] เปลี่ยนไปเหมือน [B] ใช่ไหม".
