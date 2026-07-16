"""Standalone Woolworths login — subprocess entry (legacy)."""



from __future__ import annotations



import asyncio

import sys





def main() -> int:

    try:

        from woolworths_adapter.login import login_woolworths_interactive



        asyncio.run(login_woolworths_interactive())

        print("OK")

        return 0

    except Exception as exc:

        detail = str(exc).strip() or f"{type(exc).__name__}"

        print(detail, file=sys.stderr)

        return 1





if __name__ == "__main__":

    sys.exit(main())


