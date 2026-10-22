import sys

if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    from worker.command_line import run

    run(sys.argv[1:])
