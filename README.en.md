# Get started

You may immediately get to know what the repo does by simply running the following.

**Open one terminal**, inside the repo, run the following commands (in order):
```bash
python dummy_data_producer/dummy_data.py
python dummy_data_producer/dummy_data_realtime.py
```
> The second command keeps running until you stop it by `Ctrl C`. But do not stop it yet.

Keep it running, and then **open another terminal**, inside the repo, copy the following into the terminal and hit Enter:
```bash
python trade/main.py
```

Then, you will see:

* In `data/`, in the most recent CSV (by date), a new bar is appended every 5 seconds (for demo). The bar timestamps advance by the candle interval (e.g., hourly).
* In `signals/`, in the most recent CSV (by date), immediately after the new bar’s data arrives, a signal is generated (`buy`, `sell`, or `hold`); the signal is random here.
* Both the data and the signals are randomly generated, because they serve as placeholders.

Please read on for further details.

- [Get started](#get-started)
- [Purpose](#purpose)
- [What does each part do](#what-does-each-part-do)
  - [Overview](#overview)
    - [Backtest mode](#backtest-mode)
    - [Realtime signal generation mode](#realtime-signal-generation-mode)
  - [The dummy data](#the-dummy-data)
    - [How you use the generator](#how-you-use-the-generator)
    - [The result](#the-result)
  - [The signal generating part](#the-signal-generating-part)
    - [What it consists of and what each part does](#what-it-consists-of-and-what-each-part-does)
      - [Files used for both backtesting and realtime signal generation](#files-used-for-both-backtesting-and-realtime-signal-generation)
      - [File used for backtesting](#file-used-for-backtesting)
      - [Files used for realtime signal generation](#files-used-for-realtime-signal-generation)
    - [The result](#the-result-1)
- [Detailed usage steps](#detailed-usage-steps)
  - [STEP 1: simulate a backtest](#step-1-simulate-a-backtest)
  - [STEP 2: simulate realtime signal generation](#step-2-simulate-realtime-signal-generation)
  - [STEP 3: plug in your own data](#step-3-plug-in-your-own-data)
  - [STEP 4: implement your own strategy](#step-4-implement-your-own-strategy)
- [Appendix: argument meanings](#appendix-argument-meanings)
- [Limitations and boundaties](#limitations-and-boundaties)
  - [What this framework does](#what-this-framework-does)
  - [What this framework does not provide](#what-this-framework-does-not-provide)
  - [Conceptual boundaries](#conceptual-boundaries)
    - [Scope of backtesting](#scope-of-backtesting)
    - [Signal semantics](#signal-semantics)
  - [Functional limitations (MVP scope)](#functional-limitations-mvp-scope)

# Purpose

This framework provides infrastructure for **signal generation** from OHLCV data in two modes:

* **Backtest mode**: generate one signal per historical window
* **Realtime mode**: generate one signal immediately when a new bar completes

Signals (`buy`, `sell`, `hold`) are **placeholders only**.
You are expected to implement your own strategy logic.


# What does each part do
## Overview
### Backtest mode


```text
Historical Data (CSV files)
data/asset_name/YYYY-MM-DD.csv
        │
        │  (read sequentially)
        ▼
+--------------------+
|   backtester.py    |
|--------------------|
| - loads all data   |
| - builds sliding   |
|   windows          |
+--------------------+
        │
        │  (fixed-length window one by one)
        ▼
+--------------------+
|   strategy.py      |
|--------------------|
| - receives window  |
| - computes signal  |
|   at last bar's    | 
|   timestep         |
+--------------------+
        │
        │  (signals: buy / sell / hold)
        ▼
Generated signals (stored in CSV files)
signals/asset_name/YYYY-MM-DD.csv
```

### Realtime signal generation mode

```text
Live data feed (from API or dummy generator)
        │
        │  (appends new bar)
        ▼
data/asset_name/YYYY-MM-DD.csv
        │
        │  (updates are monitored by watcher)
        ▼
+--------------------+
|    watcher.py      |
|--------------------|
| - monitors CSVs    |
| - detects new bar  |
+--------------------+
        │
        │  (notification)
        ▼
+--------------------+
|    trader.py       |
|--------------------|
| - loads most       |
|   recent window    |
+--------------------+
        │
        │  (fixed-length window one by one)
        ▼
+--------------------+
|   strategy.py      |
|--------------------|
| - receives window  |
| - computes signal  |
|   at new bar's     |
|   timestep         |
+--------------------+
        │
        │  (signals: buy / sell / hold)
        ▼
Generated signals (stored in CSV files)
signals/asset_name/YYYY-MM-DD.csv
```


## The dummy data
This part generates random data into the `data/` folder. This part is only for showing what data file structure and format the framework supports, not for generating concrete data.

For real trading tasks, you need to replace it with your API code.

Your API code should produce data with the same data file structure and format for the framework to work (details below).


```text
dummy_data_producer/
├─ dummy_data.py
└─ dummy_data_realtime.py
```

* `dummy_data.py`: Generates historical OHLCV data and writes it to CSV files to simulate a completed dataset for backtesting.
* `dummy_data_realtime.py`:
  * Reads the historical OHLCV data produced by `dummy_data.py` and infers the bar interval and the timestamp of the most recent bar.
  * Continuously appends new OHLCV bars to CSV files at the inferred interval, starting from the most recent timestamp, to simulate a live data feed for realtime processing.

### How you use the generator
1. Step 1: inside the repo, you run this to generate some data
    ```bash
    python dummy_data_producer/dummy_data.py
    ```
    For backtesting, step 1 itself it enough.
2. Step 2: then you run this to automatically add the most recent OHLCV bar continuously, just like a WebSocket API does.
    ```bash
    python dummy_data_producer/dummy_data_realtime.py
    ```
    For example, if for the day 2025-12-08 there are already OHLCV bar data for `..., 20:00–21:00, 20:00–21:00, 21:00–22:00`, then `dummy_data_realtime.py` will:
    * add the bar data for 22:00–23:00
    * wait for 5 seconds
    * add the bar data for 23:00–00:00
    * wait for 5 seconds
    * add the bar data for 00:00–01:00 (2025-12-09 from now on, and data is stored in new CSV file)
    * wait for 5 seconds
    * add the bar data for 01:00–02:00
    * ...
    * this code keeps running until you hit `Ctrl+C`.

    > *No matter what the interval in `dummy_data.py` is (minutely, hourly, or daily), `dummy_data_realtime.py` always adds a new bar every 5 seconds, for your convenience in seeing how it works. When switched to real trading tasks, the framework will automatically adapt to the API’s frequency.*


### The result

> Here `asset_name` is a placeholder; replace it with your symbol and keep the argument `data_dir` in `main.py` consistent. Details below.
> Folder structure is already per-asset for future extension; MVP runs on one asset at a time.
```text
data/
└─ asset_name/
    ├─ 2025-12-01.csv
    ├─ 2025-12-02.csv
    ├─ 2025-12-03.csv
    ├─ 2025-12-04.csv
    ├─ ...
```

Inside each file there are:


| open_time                 | close_time                | open   | high   | low   | close  | volume  |
| ------------------------- | ------------------------- | ------ | ------ | ----- | ------ | ------- |
| 2025-12-01T00:00:00+00:00 | 2025-12-01T01:00:00+00:00 | 99.98  | 100.16 | 99.84 | 100.06 | 629.43  |
| 2025-12-01T01:00:00+00:00 | 2025-12-01T02:00:00+00:00 | 100.04 | 100.05 | 99.78 | 99.85  | 705.37  |
| 2025-12-01T02:00:00+00:00 | 2025-12-01T03:00:00+00:00 | 99.88  | 100.05 | 99.86 | 100.00 | 1150.18 |
| … | … | … | … | … | … | … |



## The signal generating part
### What it consists of and what each part does


```text
trade/
├─ backtest/
│  └─ backtester.py
│
├─ realtime_trader/
│  ├─ trader.py
│  └─ watcher.py
│
├─ strategy/
│  └─ strategy.py
│
└─ main.py
```

> Despite the name, `trader.py` only orchestrates window loading + signal writing; it does not place orders.

#### Files used for both backtesting and realtime signal generation
* **`main.py`**:
  * defines the following:
    * whether we are doing backtesting or realtime signal generation
    * the parameters for the strategy, such as:
      * how many bars back in history to look at for each time step’s signal
      * how tightly the watcher should work, i.e., whether it checks for CSV updates every 0.5 seconds, 1 second, 2 seconds, etc.
      * other strategy parameters that you can define yourself (you need to add them yourself)
  * runs the backtester or the realtime trader

* **`strategy.py`**:
    * no matter whether it is in backtest mode or realtime signal generation mode, at one time, it is always given a fixed-length window of the most recent bars, 
    * and based on the OHLCV data in the window, it generates the signal for the last bar's timestamp in the window, i.e., the action (`buy`, `sell`, or `hold`) you should take immediately when seeing the new bar.

#### File used for backtesting
When doing **backtesting** (in `main.py`, the argument `work_mode` is set to `backtest`):
* **backtester.py**:
  * reads all the data from the `data/` folder, slides a window over the data, and gives each window to `strategy.py` to generate a signal, then stores the signals in `signals/`.


#### Files used for realtime signal generation
When doing **realtime signal generation** (in `main.py`, the argument `work_mode` is set to `realtime`):
* **watcher.py**:
  * notifies `trader.py` once it discovers that a new OHLCV bar has been added to the CSV of the latest date under `data/asset_name`.
* **trader.py**:
  * once notified by the watcher, locates the most recent window in the data and gives the window to `strategy.py` to get a new signal
  * stores the signal in the corresponding CSV under `signals/asset_name`
  * Note: the realtime mode simulates realtime signal generation, not order execution.


> Windows are constructed by row count, not by time continuity. If there are gaps in the data (e.g., weekends or holidays), the window simply spans a longer calendar period. Strategies should handle or validate such gaps explicitly, depending on their requirements.

### The result

```text
signals/
└─ asset_name/
    ├─ 2025-12-03.csv
    ├─ 2025-12-04.csv
    ├─ ...
```

# Detailed usage steps
## STEP 1: simulate a backtest
1. Go to `trade/main.py`
2. Change this line
    ```python
    parser.add_argument("--work_mode", type=str, default="realtime", choices=["backtest", "realtime"], help='options: ["backtest","realtime"]')
    ```
    to
    ```python
    parser.add_argument("--work_mode", type=str, default="backtest", choices=["backtest", "realtime"], help='options: ["backtest","realtime"]')
    ```
3. Generate dummy past data by running this in your terminal
    ```bash
    python dummy_data_producer/dummy_data.py
    ```
4. Start the backtest by running this in your terminal
    ```bash
    python trade/main.py
    ```
5. Check the `signals/` folder for generated signals

## STEP 2: simulate realtime signal generation
1. Go to `trade/main.py` and make sure the argument `work_mode` is set to `realtime`.
2. Generate dummy past data by running this in your terminal
    ```bash
    python dummy_data_producer/dummy_data.py
    ```
3. Start continuously generating a realtime data feed, like a WebSocket API does, by running this in your terminal
    ```bash
    python dummy_data_producer/dummy_data_realtime.py
    ```
4. To start the realtime signal generation, open another terminal (important: you do not want to stop the realtime data feed), and run this in your terminal
    ```bash
    python trade/main.py
    ```
5. Watch the updates in both `data/` and `signals/`. By default, the framework simulates a new bar and its corresponding signal every 5 seconds, no matter whether the bar is supposed to be hourly data or minutely data.
   
   *The 5 seconds here is only for demonstration purposes. In practice, for example, if your WebSocket API feeds new bar data every one hour, the trader will generate a signal every one hour. It all depends on when the new bar data is fed in.*


## STEP 3: plug in your own data

Here, you replace the random data generator with your own API data.

The data from your API code should be in the following format:
* All the data for one asset should be in the folder `data/asset_name`. Feel free to change `"asset_name"` to your actual asset name and update the `data_dir` argument in `main.py`.
* Each CSV file contains data for only one day, no matter the interval (secondly, minutely, 5-minutely, hourly, etc.).
* The CSV filename should be a date in the format `2025-12-01.csv`.
* Inside each CSV file, the headers should be `open_time`, `close_time`, `open`, `high`, `low`, `close`, `volume`.
* This part is mandatory and should never be omitted to avoid mistakes. The time format should be `2025-12-01 00:00:00+00:00`. The `+00:00` part explicitly specifies the time zone offset from UTC. This is to make the timestamps clear and avoid any confusion across time zones. For example:
    * `+00:00` = UTC (Coordinated Universal Time)
    * `+09:00` = UTC+9 (Japan Standard Time, JST)
    * `+01:00` = UTC+1 (France winter time, Central European Time, CET)
    * `+02:00` = UTC+2 (France summer time, Central European Summer Time, CEST)
  
    > I’m used to working in `+00:00` (UTC), no matter where I am in the world.


```text
data/
└─ asset_name/
    ├─ 2025-12-01.csv
    ├─ 2025-12-02.csv
    ├─ 2025-12-03.csv
    ├─ 2025-12-04.csv
    ├─ ...
```

Inside each file there are

| open_time                 | close_time                | open   | high   | low   | close  | volume  |
| ------------------------- | ------------------------- | ------ | ------ | ----- | ------ | ------- |
| 2025-12-01T00:00:00+00:00 | 2025-12-01T01:00:00+00:00 | 99.98  | 100.16 | 99.84 | 100.06 | 629.43  |
| 2025-12-01T01:00:00+00:00 | 2025-12-01T02:00:00+00:00 | 100.04 | 100.05 | 99.78 | 99.85  | 705.37  |
| 2025-12-01T02:00:00+00:00 | 2025-12-01T03:00:00+00:00 | 99.88  | 100.05 | 99.86 | 100.00 | 1150.18 |
| … | … | … | … | … | … | … |


## STEP 4: implement your own strategy
1. Replace the `Strategy` class in `trade/strategy/strategy.py`
   * If you need to pass new arguments into your strategy, define them the same way the other arguments are defined in `main.py`
2. Run backtesting and realtime signal generation as above


# Appendix: argument meanings

All arguments in the trading framework are defined in `main.py`.

| Argument              | Type    | Default              | Description                                                                                                                                                                                                           |
| ---------------------- | ------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--work_mode`          | `str`   | `"realtime"`         | Selects the operating mode of the framework. `"backtest"` runs historical, sequential signal generation over existing CSV data. `"realtime"` enables event-driven signal generation triggered by newly appended bars. |
| `--data_dir`           | `str`   | `data/asset_name`    | Path to the directory containing OHLCV CSV files for a single asset. Each CSV represents one calendar day and must follow the framework’s expected schema and timestamp format.                                       |
| `--signal_dir`         | `str`   | `signals/asset_name` | Path to the directory where generated signal CSV files are written. Signals are stored by date, mirroring the structure of `data_dir`.                                                                                |
| `--num_past_timesteps` | `int`   | `100`                | Length of the fixed historical window (number of past bars) passed to the strategy at each time step. Exactly one signal is generated per window, and each signal depends solely on its corresponding window.                                                         |
| `--poll_interval`      | `float` | `0.5`                | File-system polling interval, in seconds, used to detect newly appended OHLCV bars in real-time mode. Smaller values increase responsiveness at the cost of more frequent checks.                                     |


# Limitations and boundaties
## What this framework does

**Backtest**
* Iterates over historical OHLCV data.
* At each time step, constructs a fixed-length window of past bars.
* Generates **one signal** (`buy`, `sell`, or `hold`) for each window.
* The included strategy is a placeholder and generates **random signals** only.

**Realtime signal generation**

* Monitors incoming OHLCV data.
* When a new bar arrives, constructs the most recent fixed-length window.
* Generates **one signal** for the newly completed bar's timestep.


## What this framework does not provide

This framework **does not implement any trading strategy**.

* No real alpha logic is included.
* You must implement your own strategy in `trade/strategy/strategy.py`.


## Conceptual boundaries

### Scope of backtesting

The backtest mode does **not**:

* Simulate order execution
* Track positions
* Calculate PnL
* Model fees, slippage, or risk

Signal generation is intentionally **decoupled** from execution and evaluation.
Those concerns are expected to be implemented as independent layers.

### Signal semantics

* A **signal** is a decision (`buy`, `sell`, or `hold`) made **at the close of the most recent bar**.
* Each signal is generated **solely from a fixed-length window** of past OHLCV data.
* The framework itself is **stateless** with respect to positions.
* Any position state or memory must be handled **inside the strategy implementation**.

## Functional limitations (MVP scope)

As an MVP, the framework:

* Supports **only one asset** at a time.
* Generates signals **only from that asset’s own OHLCV data**.
* Uses a **fixed-length historical window** for all signals.
