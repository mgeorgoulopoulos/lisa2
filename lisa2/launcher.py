"""Single executable dispatch for Studio, worker, preview and release checks."""
import sys


def main():
    from .runtime import configure
    folder=configure()
    args=sys.argv[1:]
    try:
        if args and args[0]=='--worker':
            sys.argv=[sys.argv[0],*args[1:]]
            from .project_worker import main as worker
            worker()
        elif args and args[0]=='--preview':
            sys.argv=[sys.argv[0],*args[1:]]
            from .preview import main as preview
            preview()
        elif args and args[0]=='--smoke-test':
            from .release_check import main as check
            check(args[1:])
        else:
            from .app import main as studio
            studio()
        return 0
    except Exception:
        import traceback
        with (folder/'launcher-error.log').open('a',encoding='utf-8') as stream:
            traceback.print_exc(file=stream)
        if sys.stderr is not None: traceback.print_exc()
        return 1


if __name__=='__main__': raise SystemExit(main())
