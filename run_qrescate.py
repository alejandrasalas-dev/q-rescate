if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parent/'desktop'))
    from qrescate_desktop.__main__ import main
    raise SystemExit(main())
