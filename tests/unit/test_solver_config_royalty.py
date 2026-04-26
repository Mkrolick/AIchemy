from aichemy.solver.config import SolverConfig


def test_solver_config_has_royalty_defaults():
    cfg = SolverConfig()
    assert cfg.r_process == 0.0
    assert cfg.r_comp == 0.0


def test_solver_config_accepts_custom_royalties():
    cfg = SolverConfig(r_process=0.05, r_comp=0.03)
    assert cfg.r_process == 0.05
    assert cfg.r_comp == 0.03
