from griductive.dpll import DPLLSolver


def test_dpll_returns_complete_sat_assignment():
    result = DPLLSolver().solve(((1, 2), (-1, 2)), 3)
    assert result.satisfiable
    assert result.assignment is not None
    assert set(result.assignment) == {1, 2, 3}
    assert all(any(result.assignment[abs(lit)] == (lit > 0) for lit in clause) for clause in ((1, 2), (-1, 2)))


def test_dpll_detects_unsat_with_branching_and_backtracking():
    clauses = ((1, 2), (1, -2), (-1, 2), (-1, -2))
    result = DPLLSolver().solve(clauses, 2)
    assert not result.satisfiable
    assert result.assignment is None
    assert result.metrics.decisions > 0
    assert result.metrics.backtracks > 0
    assert result.metrics.conflicts > 0


def test_dpll_assumptions_are_temporary():
    solver = DPLLSolver()
    clauses = ((1, 2),)
    assert solver.solve(clauses, 2, (-1, -2)).satisfiable is False
    assert solver.solve(clauses, 2).satisfiable is True
