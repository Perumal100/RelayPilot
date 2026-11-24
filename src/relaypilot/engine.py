from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from .config import RelaySettings
from .executor import ConnectivityRequired, LocalExecutor, StopRequested
from .history import RunHistory
from .models import Event, RunResult, RunState
from .planner import PlannerRouter, UnsupportedCommand
from .policy import PolicyDenied


class RelayEngine:
    def __init__(
        self,
        downloads: Path,
        documents: Path,
        *,
        opener=None,
        page_fetcher=None,
        settings: RelaySettings | None = None,
        history: RunHistory | None = None,
    ) -> None:
        self.settings = settings or RelaySettings.defaults(downloads, documents)
        self.downloads = Path(self.settings.downloads)
        self.documents = Path(self.settings.documents)
        self._stop = threading.Event()
        self.planner = PlannerRouter()
        self.policy = self.settings.policy()
        self.opener = opener
        self.page_fetcher = page_fetcher
        self.history = history

    def request_stop(self) -> None:
        self._stop.set()

    def run(self, command: str) -> RunResult:
        self._stop.clear()
        events: list[Event] = [Event("Run started", "Explicit submit received; local planner selected.")]
        try:
            plan = self.planner.plan(command, self.downloads, self.documents)
            executor = LocalExecutor(self.policy, self._stop.is_set, self.opener, self.page_fetcher)
            context: dict[str, object] = {}
            for action in plan:
                message, evidence = executor.execute(action, context)
                events.append(Event(message, evidence))
            saved = context.get("copied_pdf")
            opened = context.get("opened_file")
            # ShellExecute accepts a launch request but cannot attest that a third-party
            # application has rendered a visible window. Keep that distinction visible.
            state = RunState.LAUNCH_REQUESTED if any(action.kind in {"open_file", "open_path"} for action in plan) else RunState.COMPLETED
            return self._finish(command, RunResult(state, events, saved_path=saved, opened_path=opened))
        except StopRequested as error:
            events.append(Event("Run stopped", str(error)))
            return self._finish(command, RunResult(RunState.STOPPED, events, reason=str(error)))
        except PolicyDenied as error:
            events.append(Event("Permission handoff required", str(error)))
            return self._finish(command, RunResult(RunState.HANDOFF, events, reason=str(error)))
        except (ConnectivityRequired, UnsupportedCommand, FileNotFoundError, FileExistsError, IOError, ValueError) as error:
            events.append(Event("Run blocked", str(error)))
            return self._finish(command, RunResult(RunState.BLOCKED, events, reason=str(error)))
        except Exception as error:  # UI reports unexpected failures without hiding them.
            events.append(Event("Run failed", repr(error)))
            return self._finish(command, RunResult(RunState.FAILED, events, reason=str(error)))

    def _finish(self, command: str, result: RunResult) -> RunResult:
        if self.history is not None:
            self.history.append(command, result)
        return result

