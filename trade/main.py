from __future__ import annotations

import argparse
from pathlib import Path
from strategy.strategy import Strategy
from backtest.backtester import Backtester
from realtime_trader.trader import RealTimeTrader


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Utility Interface Backtest Framework")

    parser.add_argument("--work_mode", type=str, default="realtime", choices=["backtest", "realtime"], help='options: ["backtest","realtime"]')
    parser.add_argument("--data_dir", type=str, default=str(root / "data" / "asset_name"), help="folder containing OHLCV csvs")
    parser.add_argument("--signal_dir", type=str, default=str(root / "signals" / "asset_name"), help="folder to write signal csvs")
    parser.add_argument("--num_past_timesteps", type=int, default=100, help="sliding window length")
    parser.add_argument("--poll_interval", type=float, default=0.5, help="folder watcher polling interval (seconds) for realtime mode")

    return parser

def main() -> None:
    args = build_parser().parse_args()

    print("Args:")
    print(args)

    strategy = Strategy(args)

    if args.work_mode == "backtest":
        backtester = Backtester(args, strategy)
        sig_df = backtester.run()
        print("backtesting completed")

    elif args.work_mode == "realtime":
        trader = RealTimeTrader(args, strategy)
        trader.start()

    else:
        # This is defensive; argparse choices already restricts values.
        raise ValueError("Invalid work_mode. Use --work_mode backtest|realtime")

if __name__ == "__main__":
    main()
