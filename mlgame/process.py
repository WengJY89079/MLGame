import importlib
import traceback

from multiprocessing import Process, Pipe
from .loops import GameMLModeExecutorProperty, MLExecutorProperty
from .exceptions import (
    GameProcessError, MLProcessError,
)

class ProcessManager:
    """
    Create and manage the processes, and set up communication channels between them

    @var _game_proc_helper The helper object for the game process
    @var _ml_proc_helpers A list storing helper objects for all ml processes
    @var _ml_proces A list storing process objects running ml processes
    """

    def __init__(self):
        self._game_executor_propty = None
        self._ml_executor_propties = []
        self._ml_procs = []

    def set_game_process(self, execution_cmd, game_cls):
        """
        Set the game process

        @param execution_cmd A `ExecutionCommand` object that contains execution config
        @param game_cls The class of the game to be executed
        """
        self._game_executor_propty = GameMLModeExecutorProperty(
            "game", execution_cmd, game_cls)

    def add_ml_process(self, name, target_module, init_args = (), init_kwargs = {}):
        """
        Add a ml process

        @param name The name of the ml process
               If it is not specified, it will be "ml_0", "ml_1", and so on.
        @param target_module The full name of the module
               to be executed in the ml process. The module must have `MLPlay` class.
        @param init_args The positional arguments to be passed to the `MLPlay.__init__()`
        @param init_kwargs The keyword arguments to be passed to the `MLPlay.__init__()`
        """
        if name == "":
            name = "ml_" + str(len(self._ml_executor_propties))

        for propty in self._ml_executor_propties:
            if name == propty.name:
                raise ValueError("The name '{}' has been used.".format(name))

        propty = MLExecutorProperty(name, target_module, init_args, init_kwargs)
        self._ml_executor_propties.append(propty)

    def start(self):
        """
        Start the processes

        The ml processes are spawned and started first, and then the main process executes
        the game process. After returning from the game process, the ml processes will be
        terminated.

        Note that there must be 1 game process and at least 1 ml process set
        before calling this function. Otherwise, the RuntimeError will be raised.
        """
        if self._game_executor_propty is None:
            raise RuntimeError("The game process is not set. Cannot start the ProcessManager")
        if len(self._ml_executor_propties) == 0:
            raise RuntimeError("No ml process added. Cannot start the ProcessManager")

        self._create_pipes()
        self._start_ml_processes()
        returncode = self._start_game_process()

        self._terminate()

        return returncode

    def _create_pipes(self):
        """
        Create communication pipes for processes
        """
        # Create pipes for Game process <-> ml process
        for ml_executor_propty in self._ml_executor_propties:
            recv_pipe_for_game, send_pipe_for_ml = Pipe(False)
            recv_pipe_for_ml, send_pipe_for_game = Pipe(False)

            self._game_executor_propty.add_comm_to_ml(
                ml_executor_propty.name,
                recv_pipe_for_game, send_pipe_for_game)
            ml_executor_propty.set_comm_to_game(
                recv_pipe_for_ml, send_pipe_for_ml)

    def _start_ml_processes(self):
        """
        Spawn and start all ml processes
        """
        for propty in self._ml_executor_propties:
            process = Process(target = _ml_process_entry_point,
                name = propty.name, args = (propty,))
            process.start()

            self._ml_procs.append(process)

    def _start_game_process(self):
        """
        Start the game process
        """
        returncode = 0
        try:
            _game_process_entry_point(self._game_executor_propty)
        except (MLProcessError, GameProcessError) as e:
            print("Error: Exception occurred in '{}' process:".format(e.process_name))
            print(e.message)
            returncode = 2

        return returncode

    def _terminate(self):
        """
        Stop all spawned ml processes if it exists
        """
        for ml_process in self._ml_procs:
            ml_process.terminate()

def _game_process_entry_point(propty: GameMLModeExecutorProperty):
    """
    The real entry point of the game process
    """
    from .loops import GameMLModeExecutor

    executor = GameMLModeExecutor(propty)
    executor.start()

def _ml_process_entry_point(propty: MLExecutorProperty):
    """
    The real entry point of the ml process
    """
    from .loops import MLExecutor

    executor = MLExecutor(propty)
    executor.start()
