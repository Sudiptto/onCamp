import logging

import azure.functions as func

from jobs.club_discovery.semester_refresh import run_semester_discovery

app = func.FunctionApp()

SEMESTER_DISCOVERY_SCHEDULE = "0 0 12 5 1,8 *"


@app.function_name(name="semester_club_discovery")
@app.timer_trigger(
    schedule=SEMESTER_DISCOVERY_SCHEDULE,
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def semester_club_discovery(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("Semester club discovery timer is past due.")

    summary = run_semester_discovery()
    logging.info("Semester club discovery completed: %s", summary)
