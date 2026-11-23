# Bàn giao — Logic Agent và tích hợp

## Hợp đồng của dự án

Nhánh `main` của `kitchauhcmus/griductive-solver` là hợp đồng tích hợp. Checkout
hiện có Engine, CNF, DPLL, CLI, web GUI, puzzle, assets và test sản phẩm từ main.
Phần Agent mở rộng dự án này; không thay thế schema chung bằng bản rút gọn.

Nhóm 5 người có thể giữ ranh giới: Engine/dữ liệu; Agent/tích hợp; clue/CNF;
DPLL; GUI/video. Khi sửa `models.py` hoặc đổi API, đối chiếu main và thống nhất
với những người dùng module đó. Không suy ra tên hoặc mức đóng góp thành viên
từ ranh giới file này.

## Dữ liệu dùng chung

Import từ `griductive.models`: `Status`, `CellInfo`, `Clue`, `RegionSpec`,
`Puzzle`, `PublicGameState`, `Submission`, `VerdictResult`. Giữ nguyên các
dataclass/parser và trường metadata cầu thủ của main. `Clue` là dataclass cụ thể,
không phải Protocol. `Puzzle` chứa dữ liệu đầy đủ; Agent không được nhận nó.

```python
PublicGameState(title, size, cells, revealed_clues, proved)
Status.CRIMINAL   # biến SAT True
Status.INNOCENT   # biến SAT False
```

`proved` vẫn là dictionary theo main. Engine trả bản sao dictionary trong mỗi
snapshot; caller phải coi snapshot là dữ liệu chỉ đọc. Agent tự sao chép container
trước khi mã hóa, không hứa mọi đối tượng lồng nhau đều bất biến. Không đưa
solution hoặc clue chưa mở vào PublicGameState.

`Classification.status is None` nghĩa là chưa có nhãn bắt buộc. Đọc
`.inconsistent` trước để phân biệt UNKNOWN với KB mâu thuẫn. Thuộc tính `.label`
trả chuỗi hiển thị. Hint xét ô chưa giải theo `(row, column, id)`.

## CNF và DPLL

```python
CNFEncoder(size, cells).encode_public_state(state)
CNFEncoder(size, cells).encode_clues(tuple_of_clues)
DPLLSolver().solve(clauses, variable_count, assumptions=())
```

Giữ các lớp kết quả đang có trong `cnf.py` và `dpll.py`; Agent nhận cấu trúc
tương thích, không yêu cầu đồng đội chuyển sang dataclass trong `contracts.py`.
CNF cần `clauses`, `primary_variables`, `auxiliary_variables`. Ánh xạ chính phải
đủ mọi ô; ID biến dương, riêng biệt, literal khác 0. Số dương nghĩa có tội, số âm
nghĩa vô tội. Agent dùng ID lớn nhất làm variable_count và bổ sung unit của
proved nếu Encoder chưa thêm. Main đang sinh ID liên tiếp nên hai cách đếm trùng nhau.

SAT trả model Boolean đầy đủ cho biến chính/phụ. UNSAT trả assignment=None.
Metrics giữ `decisions`, `propagations`, `conflicts`, `backtracks`,
`recursive_calls`, `runtime_ms`, tương thích `vars()` và `asdict()` của CLI/web.
Assumptions chỉ tồn tại trong từng lần solve. Agent gửi bản sao clauses, kiểm tra
model SAT thỏa clauses/assumptions và sao chép model/metrics. Lỗi/timeout phải
raise; không trả False thay cho lỗi. Kiểm tra model không chứng nhận được UNSAT,
vì vậy vẫn phải giữ test DPLL độc lập.

## Engine và import Controller

```python
from griductive.engine import GameController, GameEngine
```

Import này phải tiếp tục chạy như main. Chỉ có một lớp Controller triển khai
trong `controller.py`; `engine.py` re-export nó, các package export cũng giữ nguyên.
Không để GUI/CLI chạy một Controller cũ khác với Controller mà test Agent dùng.

Engine giữ đáp án, clue ẩn, load và restart. Nó cung cấp `public_state`, `solved`,
`restart()` và `reveal_after_proof(cell_id, status)`. GUI không gọi reveal trực
tiếp: Controller chỉ gọi khi đã có chứng minh. Với ô mới, reveal ghi đúng một
verdict, công bố đúng một clue ID mới, giữ nguyên bàn và thông tin công khai cũ.
Nếu nhãn không khớp, phải raise trước khi cập nhật. Controller kiểm tra kết quả
reveal; nếu phát hiện cập nhật sai thì khóa thao tác đến restart.

## Kết nối và chế độ kiểm tra

```python
from griductive.agent import LogicAgent
from griductive.cnf import CNFEncoder
from griductive.dpll import DPLLSolver
from griductive.engine import GameController, GameEngine

engine = GameEngine.load("puzzles/3x3_binary_chain.json")
agent = LogicAgent(solver=DPLLSolver(), encoder_factory=CNFEncoder)
controller = GameController(engine, agent)
```

Mặc định giữ hợp đồng main: một auto-step có ngay ô bắt buộc dùng 3 lần SAT
(KB, giả sử có tội, giả sử vô tội), tái sử dụng chứng minh Hint. Có thể bật kiểm
tra KB mới ngay sau từng reveal:

```python
controller = GameController(engine, agent, check_revealed_consistency=True)
```

Chế độ này thêm 1 SAT call mỗi lượt chấp nhận. Nếu clue mới gây mâu thuẫn, lượt
vẫn trả ACCEPTED vì chứng minh trước reveal hợp lệ, nhưng last_run_status chuyển
INCONSISTENT ngay. Mặc định không chạy kiểm tra thêm này; lần suy luận tiếp theo
hoặc `agent.check_consistency(state)` có thể phát hiện mâu thuẫn. Khi báo số liệu,
ghi rõ chế độ; demo fixture bật chế độ kiểm tra thêm.

## Thao tác GUI và kết quả

```python
controller.submit("A1", Status.CRIMINAL)
controller.hint()       # (cell_id, Classification) hoặc None; không mở thẻ
controller.auto_step()  # Submission hoặc None; mở tối đa một thẻ
controller.auto_solve(max_steps=None)
controller.restart()
```

Submission.result: ACCEPTED, NOT_PROVABLE, CONTRADICTED, INCONSISTENT hoặc
ALREADY_SOLVED. Chỉ ACCEPTED được mở clue. `last_run_status`: READY, SOLVED,
STUCK, INCONSISTENT hoặc STEP_LIMIT. max_steps đếm lượt chấp nhận của lần gọi,
không đếm truy vấn SAT/thời gian. `None` không tự chứng minh đã giải xong.

Hint không đổi bàn/trace nhưng vẫn tăng counters. `classify_all` chỉ trả ô chưa
giải; dùng check_consistency để kiểm tra toàn KB. Hint bất nhất trên bàn đã giải
hết không phải lời đề nghị mở thẻ. Web Match đang có lock: giữ cơ chế này, không
chạy đồng thời nhiều thao tác Controller. Timer không làm Solver tự nonblocking.

Trace ghi clue có trước lượt, các truy vấn tìm chứng minh, ô, nhãn và clue mới.
Query log/counters còn tính Hint, thao tác bị từ chối và uniqueness. Reset hoặc
dùng Agent riêng khi tách số liệu kiểm định khỏi chơi. Exception không được tính
thành kết quả SAT/UNSAT hợp lệ. `last_formula` là KB công khai xây gần nhất.

## Nghiệm duy nhất và kiểm thử

`check_uniqueness(public_metadata, all_clues)` trả (False,False) nếu vô nghiệm,
(True,True) nếu đúng một nghiệm trên biến chính, (True,False) nếu nhiều nghiệm.
Chỉ công cụ quản trị được lấy toàn bộ clue. Hàm bỏ proved/revealed hiện tại,
không đưa nghiệm vào Hint. Dữ kiện khởi đầu/quy luật toàn cục của đề phải được
đưa rõ vào tập ràng buộc kiểm định nếu đó là tiên đề của puzzle.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m examples.agent_demo
.\.venv\Scripts\python.exe main.py validate puzzles
```

Pytest chạy cả test function/fixture của main và unittest class của Agent.
`unittest discover` đơn lẻ bỏ sót test sản phẩm. Giữ test của main, gồm đường
giải 3×3/4×4/5×5, schema cầu thủ, no-hidden-information, CLI/web và hợp đồng 3
SAT calls cho auto-step mặc định. Fixture/oracle vét cạn chỉ dành cho test/demo;
không thay DPLL sản phẩm hoặc dùng làm benchmark của toàn đội.

## Tham chiếu

Hợp đồng hiện tại: main của
[team repository](https://github.com/kitchauhcmus/griductive-solver/tree/main).
Repo `hyt2434/Griductive-Solver` là tham khảo cấu trúc ban đầu, không thay thế
hợp đồng API hiện có của team. Kết quả chạy mới được ghi sau khi kiểm thử xong;
không xem số liệu của các lần kiểm tra cũ là xác nhận checkout hiện tại.
