# Bàn giao — Logic Agent và tích hợp

## Phạm vi cho nhóm 5 người

1. **Game Engine và dữ liệu:** sở hữu `engine.py`, dữ liệu puzzle, đáp án ẩn,
   Load/Restart, mở clue và snapshot công khai.
2. **Logic Agent và tích hợp (nhánh này):** sở hữu `agent.py`, `controller.py`,
   test cho agent và tài liệu bàn giao.
3. **Biểu diễn clue và CNF:** sở hữu `clues.py`, `regions.py`, `cnf.py`, kiểu clue
   và vùng cụ thể; mở rộng `models.py` sau khi thống nhất giao diện.
4. **DPLL:** sở hữu `dpll.py`, solver, thống kê và kiểm thử SAT độc lập.
5. **GUI và video:** sở hữu `gui.py`, kết nối thao tác người chơi với controller,
   video demo. Nhóm tự phân chia thực nghiệm và ghép báo cáo.

Đây là đề xuất ranh giới file dựa trên ảnh phân công, không xác nhận các thành
viên khác đã hoàn thành hoặc đồng ý API. Nhánh agent đã có thể chạy test độc lập.

## Hợp đồng cần giữ

`models.py` chỉ chứa dữ liệu công khai và kết quả thao tác. `Clue` hiện là
`Protocol` chỉ yêu cầu `id`: người làm CNF bổ sung dataclass/parser của mình.
Không đưa `solution`, toàn bộ puzzle hoặc clue chưa mở vào `PublicGameState`.
`proved` là mapping chỉ đọc; Engine phải trả snapshot mới sau khi cập nhật.
Clue công khai phải bất biến và so sánh bằng nội dung giữa các snapshot.

```python
PublicGameState(title, size, cells, revealed_clues, proved)
CellInfo(id, name, profession, row, column)
Status.CRIMINAL   # True
Status.INNOCENT   # False
```

`Classification.status is None` biểu diễn `UNKNOWN` (không phải verdict để nộp).
`classification.label` trả `CRIMINAL`, `INNOCENT`, `UNKNOWN`, hoặc `INCONSISTENT`.
Ô được chọn theo `(row, column, id)`; tọa độ tuân theo quy ước của Engine/CNF.

### CNF teammate

```python
CNFEncoder(size, cells).encode_public_state(state) -> CNFFormula
CNFEncoder(size, cells).encode_clues(tuple_of_clues) -> CNFFormula
```

Kết quả cần có `clauses`, `primary_variables`, `auxiliary_variables`. Có thể
dùng `CNFFormula` từ `contracts.py` hoặc dataclass tương thích. Clause là dãy
số nguyên khác 0. Số dương nghĩa là CRIMINAL; số âm là INNOCENT. Biến chính ánh
xạ **đủ mọi cell**, kể cả cell chưa xuất hiện trong clue. Mỗi biến có ID nguyên
dương riêng, không trùng với biến phụ. Agent tự thêm unit clauses của `proved`
nếu encoder chưa thêm. Không được tự thêm hidden solution hoặc hidden clue.

### DPLL teammate

```python
DPLLSolver().solve(clauses, variable_count, assumptions=()) -> SATResult
# result.satisfiable: bool
# result.assignment: mapping[int, bool] | None
# result.metrics: decisions, propagations, conflicts, backtracks,
#                 recursive_calls, runtime_ms
```

`variable_count` là ID biến lớn nhất. Mỗi lần solve phải độc lập; assumptions
không lưu qua lần gọi sau. SAT phải trả model boolean đầy đủ, UNSAT trả `None`.
Agent gửi bản sao clauses cho từng lần gọi và cộng metrics. Lỗi/timeout phải
raise exception; không dùng `False` để biểu diễn lỗi vì `False` nghĩa là UNSAT.
Agent kiểm tra model SAT có đủ biến chính/phụ, giá trị boolean, thỏa clauses và
assumptions; kết quả không hợp lệ gây `ValueError`. UNSAT phải có assignment
`None`. Kiểm tra model SAT không thay thế việc kiểm thử tính đúng của DPLL.

### Engine teammate

```python
engine.public_state -> PublicGameState
engine.solved -> bool
engine.restart() -> None
engine.reveal_after_proof(cell_id, Status) -> clue
```

`reveal_after_proof` phải kiểm tra nhãn ẩn, ghi verdict và công bố clue như một
thao tác thống nhất; nếu lỗi phải giữ nguyên trạng thái. Đây là thao tác **nội
bộ**, GUI không gọi trực tiếp. Controller chỉ gọi sau khi agent đã chứng minh.
Engine được giữ đáp án; agent không bao giờ nhận Engine hoặc puzzle đầy đủ.
Controller kiểm tra Engine thực sự ghi verdict và công bố clue để tránh vòng
lặp không tiến triển. Lỗi hợp đồng Engine được raise để sửa, không bị bỏ qua.
Mỗi lần reveal phải thêm đúng một clue ID mới, nội dung trả về phải khớp clue
được công bố; không mở thêm clue khác, đổi bàn hoặc sửa verdict/clue đã có.
Nếu controller phát hiện cập nhật sai, các thao tác tiếp theo bị chặn đến khi
gọi `restart()`: controller không thể tự hoàn tác trạng thái riêng của Engine.

### GUI teammate

```python
controller = GameController(engine, agent)
controller.submit("A1", Status.CRIMINAL)  # cũng nhận chuỗi enum hợp lệ
controller.hint()       # (cell_id, Classification) hoặc None; không mở thẻ
controller.auto_step()  # Submission hoặc None; mở tối đa một thẻ
controller.auto_solve(max_steps=None)  # danh sách Submission ACCEPTED
controller.restart()   # reset Engine, trace, counters và last_formula
```

Giữ GUI phản hồi bằng cách gọi `auto_step()` theo timer; không cần dùng vòng
lặp `auto_solve()` trên UI thread. Sau mỗi bước đọc snapshot mới để vẽ lại.
`last_run_status` là `READY`, `SOLVED`, `STUCK`, `INCONSISTENT`, hoặc `STEP_LIMIT`.
`None` từ auto-step không phải bằng chứng puzzle đã giải xong: phải đọc status.

Manual submission trả `ACCEPTED`, `NOT_PROVABLE`, `CONTRADICTED`,
`INCONSISTENT`, hoặc `ALREADY_SOLVED`. Chỉ `ACCEPTED` được mở clue. Cell/status
không hợp lệ gây `ValueError`; lỗi solver/engine được truyền lên cho UI xử lý.
Hint chỉ đọc dữ liệu và chạy SAT, không đổi game state hoặc deduction trace.
Sau **mỗi** reveal hợp lệ, controller kiểm tra KB mới ngay. Một verdict đã được
chứng minh vẫn trả `ACCEPTED`, nhưng nếu clue mới gây mâu thuẫn thì trạng thái
dừng là `INCONSISTENT`, kể cả khi vừa chạm `max_steps`.

`agent.check_consistency(state)` trả `Classification` với `inconsistent` và
truy vấn KB, dùng để kiểm tra tính nhất quán mà không chọn cell. `hint()` cũng
báo inconsistency trên bàn đã chứng minh hết ô; tuple đó không phải đề nghị mở
thẻ. `classify_all()` chỉ trả các ô chưa chứng minh, nên trên bàn hoàn tất cần
dùng `check_consistency()` nếu muốn kiểm tra KB trực tiếp.

## Trace và số liệu

`controller.trace` chứa bước đã được chấp nhận: `step`, `active_clues` **trước
khi mở**, `sat_queries` (gồm kiểm tra KB), `cell_id`, `verdict`, `revealed_clue`.
`agent.query_log` ghi các truy vấn có kết quả solver hợp lệ, kể cả thao tác bị
từ chối và uniqueness; lỗi/timeout được raise cho caller ghi nhận riêng.
`agent.stats.sat_calls` và `agent.stats.solver` là tổng kể từ lần reset gần nhất.
Hint rồi submit sẽ chạy lại SAT trên snapshot hiện tại và được tính hai lần.
Uniqueness cũng cộng counters: reset hoặc lưu chênh lệch trước khi đo từng pha.
Kiểm tra KB sau mỗi reveal thêm một SAT call và được tính vào tổng. Các call
raise exception hoặc trả kết quả sai hợp đồng không được tính như SAT/UNSAT.
`agent.last_formula` cho biết KB công khai gần nhất, gồm unit của proved;
`variable_count`, `clause_count` dùng để báo cáo kích thước tại bước đó.

## Kiểm tra nghiệm duy nhất riêng

```python
agent.check_uniqueness(public_metadata, all_clues)  # (satisfiable, unique)
# (False, False): không có nghiệm
# (True, True): đúng một nghiệm trên biến chính
# (True, False): nhiều nghiệm
```

Chỉ công cụ kiểm định puzzle được gọi API này bằng **toàn bộ clue**. Không gọi
từ Hint/Auto Solve để hỗ trợ suy luận khi chơi. Hàm không sử dụng `proved` hoặc
`revealed_clues` hiện tại, không thay KB đang chơi và không đưa model tìm được
vào Hint. Một puzzle unique vẫn có thể bị STUCK với các clue mở ban đầu.

## Tích hợp và tránh conflict

- Dùng nhánh riêng; không sửa module của nhau để đổi API mà chưa thống nhất.
- Engine có thể re-export `from .controller import GameController` nếu cần giữ
  import path như repo tham khảo. Không định nghĩa controller lần hai.
- Không copy các fixture/oracle từ `tests/support.py` vào code sản phẩm. Chúng
  chỉ kiểm tra agent; encoder sáu loại clue và DPLL vẫn là việc của teammates.
- Khi ba module thật đã có, chạy test toàn nhóm và thêm test Load puzzle JSON
  → CNF thật → DPLL thật → Controller → GUI, dùng puzzle 3×3 và 4×4 của nhóm.
- Chưa có benchmark của nhóm, GUI hoặc video trong nhánh này; không trình bày
  demo giả lập như kết quả thực nghiệm của toàn hệ thống.

## Tham chiếu

Tên package/API đối chiếu repo
[Griductive-Solver, commit 587b04c](https://github.com/hyt2434/Griductive-Solver/tree/587b04cbd56ab2f2835e9ce905e6c98ff5817187).
Thuật toán và code nhánh này được viết mới. Phân công 5 người lấy từ ảnh người
dùng cung cấp; kế hoạch 6 người cũ ngoài repository không được dùng làm chỉ dẫn.
