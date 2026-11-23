# Báo cáo chuyên đề: Logic Agent và tích hợp trong Griductive Solver

**Ngày cập nhật: 22/11/2026.** Tài liệu trình bày phần việc của vai trò
**Logic Agent và tích hợp** trong nhóm năm người. Nội dung mô tả mã hiện có,
cơ sở thuật toán, bằng chứng kiểm chứng và các giới hạn của phần bàn giao.
Hướng dẫn cài đặt, chạy chương trình và thao tác VS Code nằm trong `README.md`;
thao tác editor được giải thích thêm trong `docs/VSCODE_GUIDE.md`. Chi tiết
bàn giao nằm trong `docs/AGENT_HANDOFF.md`; cách ghép với module của đồng đội
nằm trong `docs/TEAM_INTEGRATION.md`.

## 1. Mục tiêu và phạm vi thực hiện

Griductive yêu cầu xác định nhân vật là CRIMINAL hoặc INNOCENT từ các manh mối
được công bố dần. Một nhãn trùng đáp án ẩn vẫn chưa đủ điều kiện mở thẻ: người
chơi phải chứng minh nhãn đó bằng tri thức hiện tại. Vì vậy, nhiệm vụ của agent
là phân biệt điều **có thể đúng** với điều **bắt buộc đúng**, đồng thời điều
khiển quá trình nhận manh mối mới sau mỗi kết luận hợp lệ.

Phân công năm người chia các phần thành Engine và dữ liệu; Agent và tích hợp;
biểu diễn clue và CNF; DPLL; GUI và video. Phần này thực hiện `agent.py`,
`controller.py`, các giao diện công khai, kiểm thử và tài liệu liên quan.
Controller được đặt trong file riêng để thành viên làm `engine.py` có thể
phát triển độc lập. Thực nghiệm toàn hệ thống và ghép báo cáo vẫn cần sự phối
hợp của nhóm; tài liệu này không tự xác nhận phần việc của bốn thành viên khác.

Sản phẩm của vai trò gồm phân loại ba trạng thái, kiểm tra lượt chơi, Hint,
giải tuần tự không đoán, trace, thống kê lời gọi SAT và kiểm định nghiệm duy
nhất. Bản bàn giao không chứa GUI hoàn chỉnh, bộ dữ liệu puzzle của nhóm,
encoder sáu loại clue hay DPLL sản phẩm. Những thành phần đó được kết nối qua
hợp đồng rõ ràng; oracle vét cạn trong test chỉ phục vụ kiểm chứng agent.

## 2. Mô hình tri thức và ranh giới dữ liệu

Với mỗi nhân vật `i`, đặt biến mệnh đề `x_i`. Giá trị đúng biểu diễn CRIMINAL,
giá trị sai biểu diễn INNOCENT. Tập biến chính là `X`; encoder có thể thêm tập
biến phụ `Y` khi chuyển manh mối thành CNF. Một nghiệm puzzle là phép gán trên
`X`; các phép gán khác nhau của `Y` có thể cùng biểu diễn một nghiệm puzzle.
`x_i` biểu diễn nhãn nhân vật, không biểu diễn clue của người đó đúng hay sai.
Các clue đã công bố được xem là ràng buộc của bài toán. Phần agent không tự
thêm luật “tội phạm nói dối” hoặc đảo nghĩa clue theo nhãn người sở hữu.

Literal là biến hoặc phủ định của biến. Clause là phép tuyển các literal;
CNF là phép hội các clause. Theo giao diện số nguyên, literal `j` biểu diễn
biến `j` đúng, literal `-j` biểu diễn biến đó sai. Clause `(1, -2)` tương ứng
`x_1 ∨ ¬x_2`. Unit clause `(1,)` ép `x_1` đúng. CNF không có clause là đúng
với mọi phép gán; clause rỗng là sai với mọi phép gán.

Tại bước `t`, gọi `R_t` là tập clue đã mở, `P_t` là các verdict đã chứng minh.
Cơ sở tri thức công khai được xây dựng theo:

```text
KB_t(X,Y) = CNF(R_t) ∧ AND_{(i,v) trong P_t} literal(i,v)
literal(i,CRIMINAL) = x_i
literal(i,INNOCENT) = ¬x_i
```

`PublicGameState` chứa tiêu đề, kích thước, thông tin các ô, `revealed_clues`
và `proved`. Nó không chứa `solution` hay clue chưa mở. Engine giữ dữ liệu
ẩn và tạo snapshot mới sau cập nhật. Agent chỉ nhận snapshot; controller
mới có quyền yêu cầu Engine mở thẻ sau chứng minh. Sự phân tách này giúp kiểm
tra rằng thay dữ liệu ẩn mà giữ nguyên snapshot không làm đổi Hint hiện tại.

`build_kb` sao chép phần chứa dữ liệu công khai, gọi encoder rồi thêm unit
clauses của `proved` nếu chưa có. Hàm kiểm tra ID ô, ánh xạ đủ biến chính,
biến chính/phụ không trùng và literal tham chiếu đúng biến. `proved` là mapping
chỉ đọc. Clue cụ thể do thành viên CNF cung cấp phải bất biến và so sánh được
theo nội dung; việc đóng băng container không tự đóng băng mọi đối tượng clue.

## 3. Suy diễn bằng SAT và nguyên tắc không đoán

`SAT(F)` hỏi có tồn tại phép gán thỏa công thức `F` hay không. Kết quả SAT
cung cấp một model; UNSAT cho biết không tồn tại model. Trong khi đó, hệ quả
logic `KB ⊨ x_i` yêu cầu `x_i` đúng trong **mọi** model của KB. Quan hệ dùng
để chuyển bài toán suy diễn thành truy vấn SAT là:

```text
KB ⊨ x_i   khi và chỉ khi   KB ∧ ¬x_i là UNSAT
KB ⊨ ¬x_i  khi và chỉ khi   KB ∧ x_i  là UNSAT
```

Agent kiểm tra KB nhất quán trước, sau đó chạy hai truy vấn cho ô chưa biết.
`KB ∧ x_i` SAT và `KB ∧ ¬x_i` UNSAT dẫn đến CRIMINAL. Hai kết quả đảo lại
dẫn đến INNOCENT. Nếu cả hai SAT, trạng thái là UNKNOWN: hiện có ít nhất một
model cho mỗi nhãn. UNKNOWN là thiếu bằng chứng, không phải xác suất 50% và
cũng không phải verdict được phép gửi để mở thẻ.

Ví dụ `KB = x_A ∨ x_B` có các model `(đúng, sai)`, `(sai, đúng)` và
`(đúng, đúng)`. Model đầu chứa `x_A` đúng nhưng model thứ hai chứa `x_A` sai.
Do đó A vẫn UNKNOWN. Ngược lại, `KB = x_A ∧ (¬x_A ∨ x_B)` ép cả A và B
đúng. Khi thử `¬x_B`, hai unit đối nhau xuất hiện, cho UNSAT; đây mới là
bằng chứng B là CRIMINAL.

Kiểm tra nhất quán là điều kiện bắt buộc. Với `KB = x_A ∧ ¬x_A`, cả
`KB ∧ x_B` lẫn `KB ∧ ¬x_B` đều UNSAT. Trong logic cổ điển, một tập giả thiết
mâu thuẫn kéo theo mọi mệnh đề vì không còn model phản ví dụ. Nếu bỏ bước
kiểm tra KB, chương trình có thể coi cả hai nhãn đều được chứng minh.
Triển khai trả INCONSISTENT và dừng mở thẻ ngay khi KB UNSAT, kể cả khi ô
đang hỏi đã nằm trong `proved`.

Sau KB SAT, hai nhánh cùng UNSAT là kết quả không phù hợp với logic SAT
đúng. Agent xử lý theo nhánh INCONSISTENT để chặn kết luận tiếp. Điều này
không xác định nguyên nhân lỗi; nhóm vẫn phải kiểm tra solver và dữ liệu.

## 4. Quan hệ với CNF và DPLL

Agent dùng CNF làm đầu vào; việc giải thích ngữ nghĩa clue và sinh CNF thuộc
encoder. Ví dụ `SAME(A,B)` có nghĩa hai nhãn giống nhau:

```text
x_A ↔ x_B  ≡  (¬x_A ∨ x_B) ∧ (x_A ∨ ¬x_B)
```

Cặp `(đúng, đúng)` và `(sai, sai)` thỏa cả hai clause; hai cặp khác vi phạm
một clause. Khi biết `x_A` đúng, clause thứ nhất ép `x_B` đúng. Agent chỉ
cần truy vấn SAT trên kết quả mã hóa để tìm lại hệ quả này.

`EXACTLY1({A,B})` yêu cầu đúng một người là CRIMINAL:

```text
(x_A ∨ x_B) ∧ (¬x_A ∨ ¬x_B)
```

Clause đầu loại `(sai, sai)`; clause sau loại `(đúng, đúng)`. Hai phép gán
còn lại đều hợp lệ. Vì thế clue này đứng riêng không xác định nhãn từng
người. Với ba người, `EXACTLY1({A,B,C})` gồm clause ít nhất một người
`(x_A ∨ x_B ∨ x_C)` và ba clause loại từng cặp cùng đúng:
`(¬x_A ∨ ¬x_B)`, `(¬x_A ∨ ¬x_C)`, `(¬x_B ∨ ¬x_C)`.

DPLL là thuật toán phụ thuộc do thành viên khác hiện thực. Về nguyên lý,
solver lan truyền unit clause, phát hiện clause rỗng, chọn biến chưa gán,
phân nhánh rồi quay lui khi xung đột. Ví dụ minh họa quá trình:

```text
F = (s) ∧ (¬p ∨ q) ∧ (¬p ∨ ¬q) ∧ (p ∨ r)
```

Lan truyền unit cho `s = đúng`. Giả sử heuristic chọn thử `p = đúng`:
hai clause giữa trở thành `(q)` và `(¬q)`, tạo xung đột. Solver quay lui,
thử `p = sai`; clause cuối ép `r = đúng`, còn `q` có thể nhận một trong hai
giá trị. Model hoàn chỉnh, chẳng hạn `s=đúng, p=sai, q=sai, r=đúng`, thỏa F.
Đây là ví dụ khái niệm với thứ tự thử được chọn để thấy quay lui; không phải
log chạy hay quy tắc chọn nhánh đã cài trong phần agent.

## 5. Thuật toán phân loại và tìm Hint

Thuật toán sau phản ánh `classify_cell`. `SOLVE` bao gồm kiểm tra hợp đồng
kết quả solver, ghi truy vấn và cộng metrics. Assumptions chỉ có hiệu lực
trong một lần gọi; agent không thêm chúng vĩnh viễn vào KB.

```text
CLASSIFY_CELL(state, i):
    kiểm tra i thuộc các ô công khai
    F ← BUILD_KB(state)
    nếu SOLVE(F) là UNSAT: trả INCONSISTENT
    nếu i thuộc state.proved: trả verdict đã chứng minh
    can_criminal ← SOLVE(F, assumptions=[x_i]).satisfiable
    can_innocent ← SOLVE(F, assumptions=[¬x_i]).satisfiable
    nếu can_criminal và không can_innocent: trả CRIMINAL
    nếu can_innocent và không can_criminal: trả INNOCENT
    nếu cả hai SAT: trả UNKNOWN
    ngược lại: trả INCONSISTENT
```

`classify_all` dựng một KB và kiểm tra nhất quán một lần, rồi dùng cùng công
thức cho mọi ô chưa chứng minh. Hàm không gọi lặp `classify_cell` vì cách đó
sẽ dựng lại KB và kiểm tra base nhiều lần. Kết quả chỉ gồm ô chưa chứng minh;
khi bàn đã hoàn tất, muốn kiểm tra KB trực tiếp cần `check_consistency`.

Hint cũng dùng một KB cho lần tìm kiếm hiện tại:

```text
HINT(state):
    F ← BUILD_KB(state); kiểm tra SOLVE(F)
    U ← các ô chưa chứng minh, sắp theo (row, column, id)
    nếu F UNSAT: trả ô đầu phù hợp kèm INCONSISTENT
    lần lượt xét i trong U:
        chạy hai truy vấn polarity trên F
        nếu i forced hoặc kết quả inconsistent: trả i và classification
    trả None
```

Nếu mọi ô đã chứng minh nhưng KB mâu thuẫn, Hint trả ô đầu theo cùng thứ tự
kèm cờ INCONSISTENT; tuple này không phải đề nghị mở lại thẻ. Bàn nhất quán
đã hoàn tất trả `None`. Trạng thái có danh sách ô rỗng được xem là dữ liệu
không hợp lệ và bị từ chối. Chương trình không dùng cache: Hint rồi submit sẽ chạy lại truy vấn từ
snapshot mới nhất. Cách chọn xác định thuận tiện cho kiểm thử và đối chiếu
trace, nhưng chưa tối ưu số truy vấn hoặc lượng thông tin của clue sắp mở.

## 6. Ví dụ suy luận và mở clue đầy đủ

Xét mô hình giảng giải bốn ô `A1, B1, A2, B2`; đây là ví dụ nhỏ, không thay
thế yêu cầu kiểm thử puzzle 3×3 và 4×4. Đặt lần lượt các biến `p,q,r,s`.
Ánh xạ số nguyên là `A1→1`, `B1→2`, `A2→3`, `B2→4`; chẳng hạn
`SAME(A1,B1)` tạo `(-1,2)` và `(1,-2)`.
Ban đầu A1 đã được chứng minh CRIMINAL và clue của A1 là `SAME(A1,B1)`.
Hai thông tin này đều công khai, nên:

```text
KB_0 = p ∧ (¬p ∨ q) ∧ (p ∨ ¬q)
```

Các model của KB có `p=q=đúng`, còn `(r,s)` có thể là cả bốn tổ hợp.
Agent biết nhãn A1, chứng minh được B1, đồng thời vẫn giữ A2 và B2 UNKNOWN.
Nếu người chơi gọi A2 là CRIMINAL lúc này, controller trả NOT_PROVABLE;
gọi A2 là INNOCENT cũng bị từ chối cùng lý do. Nếu gọi B1 là INNOCENT,
controller trả CONTRADICTED vì nhãn ngược lại đã bị ép buộc. Các thao tác
bị từ chối không mở clue và không thêm deduction step.

**Bước 1.** Hint chọn B1. `KB_0 ∧ q` SAT; `KB_0 ∧ ¬q` UNSAT.
Controller chấp nhận CRIMINAL và Engine mở `c_B1`, có nội dung
`EXACTLY1({B1,A2})`. KB mới chứa verdict `q` và:

```text
(q ∨ r) ∧ (¬q ∨ ¬r)
```

Vì `q` đúng, clause thứ hai ép `r` sai. B2 vẫn tự do. Chỉ sau khi clue này
được công bố, A2 mới trở thành INNOCENT; dùng nó để chứng minh ở bước trước
sẽ vi phạm quy trình chơi.

**Bước 2.** Agent thử A2: `KB_1 ∧ r` UNSAT, `KB_1 ∧ ¬r` SAT.
Controller chấp nhận INNOCENT và mở `c_A2: DIFFERENT(A2,B2)`, có CNF:

```text
(r ∨ s) ∧ (¬r ∨ ¬s)
```

Verdict `¬r` khiến clause đầu ép `s` đúng. Sau reveal, kiểm tra KB mới
vẫn SAT. **Bước 3**, B2 được chứng minh CRIMINAL; clue `c_B2: FACT(B1,
CRIMINAL)` thêm `(q)`, phù hợp tri thức đã có. Mọi ô đã chứng minh và KB
cuối nhất quán nên trạng thái là SOLVED.

Nếu chỉ chạy chuỗi tự động này, mỗi bước dùng một query base, hai query
polarity và một query kiểm tra sau reveal: tổng cộng 12 lời gọi SAT hợp lệ
cho ba verdict mới. Các lượt thử thủ công hoặc Hint riêng được nêu để giải
thích ở trên không nằm trong tổng 12. Chúng sẽ làm tăng counters nếu thực
sự được gọi. Nếu thay clue cuối bằng FACT(A1, INNOCENT), verdict B2 vẫn
đã được chứng minh từ KB trước, nhưng KB sau reveal trở thành mâu thuẫn;
kết quả lượt là ACCEPTED và trạng thái dừng là INCONSISTENT.

## 7. Kiểm tra lượt chơi và giao thức tích hợp

`GameController.submit` kiểm tra cell/status hợp lệ, lấy snapshot và nhờ
agent phân loại. KB mâu thuẫn trả INCONSISTENT; ô đã chứng minh trả
ALREADY_SOLVED sau khi vẫn kiểm tra KB. Ô UNKNOWN trả NOT_PROVABLE.
Một verdict ngược nhãn forced trả CONTRADICTED. Chỉ verdict khớp kết luận
forced được chuyển đến `engine.reveal_after_proof`.

Ngay trước reveal, controller so sánh snapshot hiện tại với snapshot đã
dùng để chứng minh, tránh dùng kết quả cũ sau khi bàn thay đổi. Sau reveal,
controller kiểm tra board được giữ nguyên, verdict cũ không bị sửa, chỉ
đúng một ô mới được chứng minh và chỉ đúng một clue ID mới được công bố.
Clue trả về phải khớp nội dung clue xuất hiện trong snapshot mới. Việc kiểm
tra cả ID và nội dung ngăn trường hợp Engine trả một clue nhưng công bố
một nội dung khác.

Nếu controller phát hiện snapshot trả về sau reveal sai hợp đồng, nó raise
exception và chặn lượt tiếp theo đến khi restart. Nó không tự hoàn tác dữ
liệu riêng bên trong Engine. Engine phải bảo đảm thao tác nguyên tử: khi
tự phát hiện lỗi, trạng thái giữ nguyên. Exception do chính Engine hoặc
solver phát sinh được truyền lên caller, không tự kích hoạt cơ chế chặn này.
Với reveal hợp lệ, controller ghi trace rồi gọi
`check_consistency` trên snapshot mới ngay, bao gồm cả bước cuối và bước
vừa chạm giới hạn. Vì thế clue mới gây mâu thuẫn không bị che bởi SOLVED
hoặc STEP_LIMIT.

`auto_step` mở tối đa một thẻ. `auto_solve` lặp bước này cho đến SOLVED,
STUCK, INCONSISTENT hoặc giới hạn số bước được chấp nhận. `max_steps=0`
không mở thẻ; trên bàn chưa hoàn tất, hàm trả STEP_LIMIT mà không bắt buộc
chạy một query mới. Lỗi solver, timeout hoặc lỗi Engine được truyền lên
caller; chúng không được diễn giải thành UNSAT. GUI có thể gọi từng
`auto_step` theo timer để cập nhật màn hình giữa các bước. Timer không tự
làm SAT chạy bất đồng bộ; khi query lâu, cần worker riêng và cập nhật giao
diện trên UI thread. Không chạy hai thao tác controller đồng thời hoặc
restart khi worker chưa kết thúc.

```text
AUTO_SOLVE(limit):
    kiểm tra limit hợp lệ; results ← []
    lặp:
        state ← engine.public_state
        nếu mọi ô đã proved:
            HINT(state) để cập nhật SOLVED hoặc INCONSISTENT; dừng
        nếu đã nhận đủ limit bước: đặt STEP_LIMIT; dừng
        result ← AUTO_STEP()  # Hint, chứng minh, reveal, kiểm tra KB mới
        nếu result là None: dừng
        thêm result vào results
        nếu trạng thái khác READY: dừng
    trả results
```

## 8. Trace, giao diện và thống kê

Một `DeductionStep` lưu số bước, ID clue đang hoạt động **trước reveal**,
chuỗi query SAT, cell, verdict và ID clue vừa mở. Trong ví dụ, trace đầu
ghi `c_A1` là active, B1 là CRIMINAL và `c_B1` là clue mới. Việc ghi đúng
thời điểm cho phép kiểm tra rằng bằng chứng không sử dụng clue được mở
sau kết luận. Query của Hint còn chứa các ô UNKNOWN đã thử trước khi gặp
ô forced. Trace là nhật ký thao tác và truy vấn, chưa phải chứng chỉ UNSAT
có thể kiểm tra độc lập bằng một proof checker.

`agent.query_log` chứa các truy vấn có kết quả hợp lệ, kể cả từ lượt bị
từ chối và kiểm định uniqueness. Query kiểm tra sau reveal nằm trong log
và counters; nó không được ghép ngược vào bằng chứng của verdict trước.
`AgentStats` cộng `sat_calls` và các trường solver: decisions, propagations,
conflicts, backtracks, recursive_calls, runtime_ms. Restart xóa tiến trình,
trace, counters và `last_formula`.

Hợp đồng encoder yêu cầu `encode_public_state(state)` và
`encode_clues(clues)` trả clauses cùng hai ánh xạ biến. Hợp đồng solver là
`solve(clauses, variable_count, assumptions)`, trả cờ boolean, model và
metrics. `variable_count` là ID biến lớn nhất; số lượng biến chính/phụ cần
đọc riêng từ độ dài từng mapping. `Classification.status=None` biểu diễn
UNKNOWN khi `inconsistent=False`; cờ mâu thuẫn phải được đọc riêng.

Agent gửi bản sao clauses cho từng SAT call và sao chép kết quả để solver
tái sử dụng object không làm đổi query trước. SAT phải cung cấp đủ giá trị
boolean cho mọi biến chính/phụ, thỏa clauses và assumptions. UNSAT phải có
model `None`. Vi phạm gây lỗi hợp đồng; các lời gọi lỗi không được tính như
kết quả SAT/UNSAT hợp lệ. Kiểm tra model giúp phát hiện lỗi trả nghiệm nhưng
không chứng minh được tính đúng của mọi kết luận UNSAT từ DPLL.

## 9. Kiểm định tính duy nhất bằng phép chặn nghiệm

Uniqueness trả lời toàn bộ clue có xác định một bộ nhãn duy nhất hay không.
Đây là công cụ kiểm định riêng được phép nhận `all_clues`; Hint và Auto Solve
không gọi nó để lấy thông tin ẩn. Hàm bỏ qua `proved`, tập reveal hiện tại
và không thay `last_formula` đang dùng khi chơi.
Nếu nhãn cho sẵn ban đầu hoặc luật toàn cục được định nghĩa là tiên đề của
puzzle, bộ kiểm định phải đưa chúng rõ ràng vào các ràng buộc mã hóa từ
`all_clues`. Hàm không tự lấy chúng từ `state.proved`, cũng không đọc đáp án
ẩn để làm hẹp tập nghiệm. Vì vậy cần kiểm tra tính đầy đủ của đầu vào kiểm định.

Mã hóa toàn bộ clue thành `F(X,Y)` rồi gọi SAT. UNSAT trả `(False,False)`.
Nếu có model M, tạo **một clause tuyển** chặn phép gán biến chính hiện tại:

```text
B_M = OR_{x thuộc X} (¬x nếu M[x]=đúng; x nếu M[x]=sai)
```

Mọi literal của B sai tại chính phép gán M trên X, nên phép gán đó bị loại.
Một phép gán khác ít nhất một biến chính làm ít nhất một literal đúng và
được giữ lại. `F ∧ B_M` UNSAT cho kết quả `(True,True)`; SAT cho
`(True,False)`. Hàm dùng một hoặc hai SAT calls tùy F có nghiệm hay không.

```text
CHECK_UNIQUENESS(metadata, all_clues):
    F ← ENCODE_CLUES(all_clues)  # không dùng proved/revealed của lúc chơi
    first ← SOLVE(F)
    nếu first không satisfiable: trả (False, False)
    B ← một clause, chứa literal ngược first.assignment[x] với mọi x chính
    second ← SOLVE(F với clause B)
    trả (True, không second.satisfiable)
```

Ví dụ M có `p=đúng, q=sai`, clause chặn là `(¬p ∨ q)`. Dùng
`¬p ∧ q` sẽ ép **cả hai** biến đảo giá trị, chỉ xét một trường hợp khác
và có thể bỏ sót nghiệm thứ hai. Do đó OR là điểm thiết yếu của thuật toán.

Biến phụ phải được loại khỏi clause chặn. Với `F(p,y)=p` và y không bị
ràng buộc, hai model đầy đủ `(p=đúng,y=sai)` và `(p=đúng,y=đúng)` cùng một
nhãn puzzle. Chặn cả p và y có thể tìm lại p đúng với y đổi, rồi báo nhầm
nhiều nghiệm. Chặn riêng `(¬p)` làm F UNSAT và xác nhận đúng một nghiệm
trên biến chính.

Một puzzle unique vẫn có thể STUCK khi chơi. Chẳng hạn clue chưa mở mới
chứa FACT(A, CRIMINAL), trong khi KB công khai không ràng buộc A. Toàn bộ
clue xác định A, nhưng agent chưa được dùng clue đó. Uniqueness và khả năng
giải tuần tự từ trạng thái ban đầu vì vậy cần được kiểm tra riêng.

## 10. Tính đúng, tiến triển và chi phí

Giả sử encoder biểu diễn đúng clue và DPLL trả đúng SAT/UNSAT. Nếu agent
kết luận CRIMINAL, KB đã SAT và `KB ∧ ¬x_i` UNSAT. Không model nào của KB
gán `x_i` sai; verdict do đó đúng trong mọi khả năng công khai. Lập luận
đối xứng cho INNOCENT. Nếu UNKNOWN, cả hai nhãn còn khả dĩ nên dừng không
đoán là hành vi cần thiết. Kiểm tra model và giao thức reveal hỗ trợ thực
thi, nhưng không thay thế hai giả thiết về encoder và DPLL.

Với N ô và k ô đã chứng minh, mỗi reveal hợp lệ thêm đúng một ô mới.
Đại lượng `N-k` giảm một và không âm, nên số bước được chấp nhận tối đa
là `N-k` ban đầu. Điều kiện này ngăn vòng lặp không tiến triển do Engine
không ghi verdict. Kết luận dừng giả định mỗi lần gọi solver/Engine kết thúc;
timeout cần cơ chế riêng của module phụ thuộc. Nếu còn ô mà không có ô
forced, trạng thái STUCK không khẳng định puzzle vô nghiệm.

Với n ô chưa giải và KB nhất quán, `classify_all` dùng `1+2n` query.
Hint tìm thấy ô forced ở vị trí j dùng `1+2j`; không tìm thấy dùng `1+2n`.
KB mâu thuẫn chỉ cần một query. Phân loại ô đã proved cần một query base.
Reveal được chấp nhận thêm một query kiểm tra KB mới. Nếu mỗi bước đầu tiên
đều forced, như demo chuỗi 3×3, chín verdict mới dùng 36 calls.

Trong trường hợp mỗi Hint quét nhiều ô, tổng số query của quá trình có thể
tăng theo bậc hai số ô. Đây chỉ là số lần gọi SAT; chi phí từng lần DPLL có
thể tăng theo hàm mũ số biến, gồm cả biến phụ. Kiểm tra model cần đọc clauses
và giá trị các biến. `runtime_ms` cộng từ solver chỉ đo phần solver công bố,
không tự bao gồm encoder, controller, GUI hay thời gian người chơi. Đo toàn
pipeline cần bộ đếm thời gian riêng và tách pha uniqueness khỏi pha chơi.

## 11. Bằng chứng kiểm chứng

Biên bản kiểm định hiện có ghi **64 test đạt**. Test dùng `unittest`,
fixture Engine/CNF và oracle vét cạn cho công thức nhỏ. Các nhóm kiểm tra
bao gồm forced/UNKNOWN/INCONSISTENT, không mở thẻ khi từ chối, cô lập
assumptions, Hint không đổi trạng thái, restart, trace, chuỗi reveal 3×3/4×4
và điều kiện dừng. Regression còn bao phủ model SAT sai, thiếu biến phụ,
vi phạm assumptions, object kết quả solver bị tái sử dụng và clue cuối
gây mâu thuẫn.

Bộ truth-table so sánh trực tiếp mọi công thức thuộc phạm vi hữu hạn:
tối đa hai clause khác nhau trên ba biến, mỗi biến xuất hiện dương, âm hoặc
không xuất hiện trong một clause. Có 27 clause khả dĩ, gồm clause rỗng;
chọn không, một hoặc hai clause tạo `1+27+351=379` công thức. Hai ánh xạ
biến chính/phụ cho 758 trường hợp công thức–mapping. Chín tổ hợp public
verdict của hai ô tạo **6.822 trạng thái**, được đối chiếu nhãn và Hint
với model tính bằng bảng chân trị. Đây là kiểm tra có giới hạn, không phải
chứng minh bằng vét cạn cho mọi puzzle hay mọi CNF.

Một harness riêng đã nối mã agent/controller/contracts với encoder, DPLL,
Engine và bốn fixture của repo tham khảo tại commit đã chốt. Hai fixture
`3x3_binary_chain`, `3x3_counting_chain` cho unique và SOLVED với tám verdict
mới; hai fixture `4x4_easy_training`, `4x4_medium_links` cho unique và SOLVED
với mười lăm verdict mới. Mỗi fixture đã có một ô mở ban đầu. Bằng chứng
này kiểm tra khả năng tương thích API, không xác nhận module tương lai
của đồng đội và không phải benchmark của nhóm. Chi tiết nằm trong
`docs/VALIDATION.md`; runtime oracle không được báo như runtime DPLL.

## 12. Giới hạn và công việc tích hợp còn lại

Phần agent chưa có incremental SAT, cache, UNSAT core, proof certificate
hay heuristic chọn clue có giá trị thông tin cao. Dựng lại KB và sao chép
clauses ưu tiên tính cô lập trong tích hợp ban đầu. Tính đúng cuối cùng
phụ thuộc ngữ nghĩa encoder, solver UNSAT và dữ liệu Engine; model checker
không phát hiện được mọi lỗi ở các thành phần đó.

Nhóm cần tích hợp module sản phẩm, kiểm tra sáu clue và hai mở rộng, chạy
puzzle 3×3/4×4 của nhóm, đo số liệu trên cùng cấu hình và lưu lỗi/timeout.
GUI, video, báo cáo tổng thể, thông tin thành viên và tỷ lệ đóng góp cần
được nhóm xác nhận riêng. Tài liệu này không gán tên, MSSV, phần trăm hoàn
thành hay kết quả thực nghiệm chưa có bằng chứng.

## 13. Các câu hỏi giải thích thuật toán

**Vì sao tìm được model chưa được kết luận nhãn?** Một model chỉ chứng minh
khả năng tồn tại. Kết luận cần loại mọi model của nhãn ngược bằng UNSAT.

**Muốn chứng minh CRIMINAL phải thử assumption nào?** Thử `¬x_i` và yêu cầu
UNSAT, sau khi xác nhận KB SAT. Query `x_i` SAT chỉ cho biết CRIMINAL khả dĩ.

**UNKNOWN khác INCONSISTENT thế nào?** UNKNOWN có model cho cả hai nhãn;
INCONSISTENT không có model cho chính KB. Hai trường hợp cần thông báo khác.

**Bước được ACCEPTED mà hệ thống INCONSISTENT có mâu thuẫn không?** Verdict
được chứng minh từ KB trước. Clue vừa mở có thể làm KB sau mâu thuẫn;
controller giữ trace bước đã hợp lệ và dừng để xử lý dữ liệu hoặc module.

**Vì sao uniqueness không dùng verdict đang chơi?** Các verdict có thể làm
hẹp tập nghiệm, che giấu việc toàn bộ clue vốn chưa xác định duy nhất.
Kiểm định đầy đủ phải dựa vào đúng tập clue cần đánh giá.

**Agent có tự viết DPLL không?** Phần này xây thuật toán suy diễn và tích
hợp trên giao diện DPLL. Thành viên DPLL viết solver; oracle test độc lập
giúp kiểm chứng agent trong lúc solver thật chưa được tích hợp.

**Vì sao Hint rồi submit tăng SAT calls hai lần?** Không có cache kết quả.
Submit chứng minh lại trên snapshot hiện tại; counters ghi đúng các lần
chạy thực tế, bao gồm một query kiểm tra sau reveal được chấp nhận.

## 14. Nguồn tham chiếu và ghi nhận hỗ trợ

Yêu cầu phạm vi lấy từ đề **AI – Project 2** người dùng cung cấp, đặc biệt
mục 4.1 và 4.4, cùng ảnh phân công nhóm năm người. Tên package, tên API và
đối chiếu tương thích tham khảo
[Griductive-Solver tại commit 587b04cbd56ab2f2835e9ce905e6c98ff5817187](https://github.com/hyt2434/Griductive-Solver/tree/587b04cbd56ab2f2835e9ce905e6c98ff5817187).
Code nhánh agent được viết mới; ứng dụng, báo cáo và assets của repo tham
khảo không được đưa vào phần bàn giao này.

Codex hỗ trợ thiết kế giao diện, hiện thực agent/controller, xây kiểm thử,
rà lỗi và soạn thảo tài liệu. Thành viên phụ trách cần đọc, chạy lại kiểm
thử, giải thích thuật toán và ghi nhận hỗ trợ AI theo quy định học phần.
Các số liệu trong tài liệu là bằng chứng kiểm chứng chức năng đã lưu;
không có số liệu benchmark toàn hệ thống, danh tính hay mức đóng góp được
tự suy diễn để điền vào báo cáo nhóm.
