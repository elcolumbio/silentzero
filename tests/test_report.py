from silentzero import Ledger, Reading, health, record_run, run_log, stock
from silentzero.gates import Verdict


def test_exit_code_is_what_a_scheduler_reads():
    assert health(stock("x", 10, floor=1)).exit_code == 0
    assert health(stock("x", 0, floor=1)).exit_code == 1


def test_the_report_names_the_failing_gate():
    text = health(stock("corpus", 1, floor=500), Verdict("coverage", True, "fine")).text()
    assert "failing gate(s): stock" in text
    assert "no artefact is produced from data that fails a gate." in text


def test_health_accepts_a_sequence_of_verdicts():
    assert len(health([stock("a", 2, floor=1), stock("b", 2, floor=1)]).verdicts) == 2


def test_a_gap_in_the_run_log_is_visible_as_a_gap():
    """Without a run log a failure is only a gap, and a gap looks like 'not yet done'."""
    led = Ledger()
    record_run(led, [Reading.found("a", 3)], label="monday")
    unfinished = led.start_run("tuesday")          # crashed mid-run, never finished
    led.record(unfinished, Reading.found("a", 3))
    text = run_log(led)
    assert "did not finish" in text
    assert "monday" in text and "tuesday" in text
    led.close()
