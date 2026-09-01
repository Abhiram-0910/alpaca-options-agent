# Strategy Graveyard

Every backtest validation run for every strategy/symbol combination, pass or fail, with the real numbers behind the verdict. A FAIL here means don't re-test this combination on the same data expecting a different answer -- either the underlying, the strategy, or the market regime changed.

## cash_secured_put / AAPL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6265
- profit_factor: 1.342
- sharpe: 1.679
- mean_return_pct: 0.00323
- total_pnl_dollars: 4417.01
- max_drawdown_dollars: -3566.71
- exit_reason_breakdown: {'expiration': 52, 'stop_loss': 31}
- mean-return 95% bootstrap CI: (-0.00076, 0.00706)
- sharpe 95% bootstrap CI: (-0.367, 3.827)
- rejection reasons: mean-return 95% bootstrap CI (-0.00076, 0.00706) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.367, 3.827) does not exclude zero (lower bound must be > 0)

## covered_call / AAPL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4217
- profit_factor: 0.697
- sharpe: -1.627
- mean_return_pct: -0.00326
- total_pnl_dollars: -5187.85
- max_drawdown_dollars: -5779.86
- exit_reason_breakdown: {'stop_loss': 48, 'expiration': 35}
- mean-return 95% bootstrap CI: (-0.00717, 0.00078)
- sharpe 95% bootstrap CI: (-3.536, 0.422)
- rejection reasons: mean-return 95% bootstrap CI (-0.00717, 0.00078) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.536, 0.422) does not exclude zero (lower bound must be > 0)

## long_directional / AAPL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2169
- profit_factor: 0.936
- sharpe: 0.556
- mean_return_pct: 0.14946
- total_pnl_dollars: -1870.79
- max_drawdown_dollars: -10133.79
- exit_reason_breakdown: {'expiration': 34, 'stop_loss': 49}
- mean-return 95% bootstrap CI: (-0.33741, 0.70275)
- sharpe 95% bootstrap CI: (-1.901, 2.112)
- rejection reasons: mean-return 95% bootstrap CI (-0.33741, 0.70275) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.901, 2.112) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / AAPL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6024
- profit_factor: 1.192
- sharpe: 0.381
- mean_return_pct: 0.01632
- total_pnl_dollars: 1554.57
- max_drawdown_dollars: -2032.3
- exit_reason_breakdown: {'expiration': 50, 'stop_loss': 33}
- mean-return 95% bootstrap CI: (-0.07027, 0.09868)
- sharpe 95% bootstrap CI: (-1.556, 2.649)
- rejection reasons: mean-return 95% bootstrap CI (-0.07027, 0.09868) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.556, 2.649) does not exclude zero (lower bound must be > 0)

## iron_condor / AAPL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3373
- profit_factor: 1.283
- sharpe: -1.039
- mean_return_pct: -0.02712
- total_pnl_dollars: 1253.2
- max_drawdown_dollars: -833.43
- exit_reason_breakdown: {'stop_loss': 55, 'expiration': 28}
- mean-return 95% bootstrap CI: (-0.07619, 0.02564)
- sharpe 95% bootstrap CI: (-2.948, 1.026)
- rejection reasons: mean-return 95% bootstrap CI (-0.07619, 0.02564) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.948, 1.026) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / AAPL -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5263
- profit_factor: 0.456
- sharpe: -3.324
- mean_return_pct: -0.11641
- total_pnl_dollars: -5016.37
- max_drawdown_dollars: -5521.67
- exit_reason_breakdown: {'time_exit': 61, 'stop_loss': 15}
- mean-return 95% bootstrap CI: (-0.1852, -0.05057)
- sharpe 95% bootstrap CI: (-4.971, -1.652)
- rejection reasons: mean-return 95% bootstrap CI (-0.1852, -0.05057) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.971, -1.652) does not exclude zero (lower bound must be > 0)

## cash_secured_put / MSFT -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4819
- profit_factor: 1.336
- sharpe: 1.445
- mean_return_pct: 0.00227
- total_pnl_dollars: 6133.3
- max_drawdown_dollars: -4994.07
- exit_reason_breakdown: {'stop_loss': 43, 'expiration': 40}
- mean-return 95% bootstrap CI: (-0.00071, 0.00543)
- sharpe 95% bootstrap CI: (-0.484, 3.474)
- rejection reasons: mean-return 95% bootstrap CI (-0.00071, 0.00543) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.484, 3.474) does not exclude zero (lower bound must be > 0)

## covered_call / MSFT -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4699
- profit_factor: 0.695
- sharpe: -1.341
- mean_return_pct: -0.00303
- total_pnl_dollars: -9488.83
- max_drawdown_dollars: -13535.88
- exit_reason_breakdown: {'expiration': 39, 'stop_loss': 44}
- mean-return 95% bootstrap CI: (-0.00775, 0.00119)
- sharpe 95% bootstrap CI: (-2.929, 0.659)
- rejection reasons: mean-return 95% bootstrap CI (-0.00775, 0.00119) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.929, 0.659) does not exclude zero (lower bound must be > 0)

## long_directional / MSFT -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2289
- profit_factor: 0.899
- sharpe: -0.498
- mean_return_pct: -0.09797
- total_pnl_dollars: -4342.65
- max_drawdown_dollars: -18925.21
- exit_reason_breakdown: {'expiration': 33, 'stop_loss': 50}
- mean-return 95% bootstrap CI: (-0.45178, 0.31058)
- sharpe 95% bootstrap CI: (-3.533, 1.262)
- rejection reasons: mean-return 95% bootstrap CI (-0.45178, 0.31058) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.533, 1.262) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / MSFT -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4819
- profit_factor: 1.058
- sharpe: -0.427
- mean_return_pct: -0.01554
- total_pnl_dollars: 787.18
- max_drawdown_dollars: -3760.66
- exit_reason_breakdown: {'stop_loss': 43, 'expiration': 40}
- mean-return 95% bootstrap CI: (-0.08694, 0.05485)
- sharpe 95% bootstrap CI: (-2.396, 1.616)
- rejection reasons: mean-return 95% bootstrap CI (-0.08694, 0.05485) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.396, 1.616) does not exclude zero (lower bound must be > 0)

## iron_condor / MSFT -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2892
- profit_factor: 0.83
- sharpe: -1.568
- mean_return_pct: -0.04034
- total_pnl_dollars: -1608.89
- max_drawdown_dollars: -3247.24
- exit_reason_breakdown: {'stop_loss': 59, 'expiration': 24}
- mean-return 95% bootstrap CI: (-0.0911, 0.0106)
- sharpe 95% bootstrap CI: (-3.474, 0.452)
- rejection reasons: mean-return 95% bootstrap CI (-0.0911, 0.0106) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.474, 0.452) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / MSFT -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5395
- profit_factor: 0.39
- sharpe: -2.792
- mean_return_pct: -0.09122
- total_pnl_dollars: -8732.71
- max_drawdown_dollars: -8732.71
- exit_reason_breakdown: {'time_exit': 64, 'stop_loss': 12}
- mean-return 95% bootstrap CI: (-0.16271, -0.02879)
- sharpe 95% bootstrap CI: (-4.536, -1.018)
- rejection reasons: mean-return 95% bootstrap CI (-0.16271, -0.02879) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.536, -1.018) does not exclude zero (lower bound must be > 0)

## cash_secured_put / NVDA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5301
- profit_factor: 1.2
- sharpe: 0.863
- mean_return_pct: 0.00297
- total_pnl_dollars: 2607.06
- max_drawdown_dollars: -4822.03
- exit_reason_breakdown: {'stop_loss': 39, 'expiration': 44}
- mean-return 95% bootstrap CI: (-0.00429, 0.0098)
- sharpe 95% bootstrap CI: (-1.186, 3.128)
- rejection reasons: mean-return 95% bootstrap CI (-0.00429, 0.0098) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.186, 3.128) does not exclude zero (lower bound must be > 0)

## covered_call / NVDA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4458
- profit_factor: 1.024
- sharpe: -0.292
- mean_return_pct: -0.0008
- total_pnl_dollars: 312.26
- max_drawdown_dollars: -3982.07
- exit_reason_breakdown: {'expiration': 38, 'stop_loss': 45}
- mean-return 95% bootstrap CI: (-0.00592, 0.00476)
- sharpe 95% bootstrap CI: (-2.165, 1.781)
- rejection reasons: mean-return 95% bootstrap CI (-0.00592, 0.00476) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.165, 1.781) does not exclude zero (lower bound must be > 0)

## long_directional / NVDA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2169
- profit_factor: 0.635
- sharpe: -0.554
- mean_return_pct: -0.10344
- total_pnl_dollars: -11687.22
- max_drawdown_dollars: -16743.95
- exit_reason_breakdown: {'expiration': 34, 'stop_loss': 49}
- mean-return 95% bootstrap CI: (-0.45103, 0.27368)
- sharpe 95% bootstrap CI: (-3.253, 1.238)
- rejection reasons: mean-return 95% bootstrap CI (-0.45103, 0.27368) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.253, 1.238) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / NVDA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5181
- profit_factor: 0.99
- sharpe: 0.209
- mean_return_pct: 0.00854
- total_pnl_dollars: -88.57
- max_drawdown_dollars: -3105.74
- exit_reason_breakdown: {'stop_loss': 40, 'expiration': 43}
- mean-return 95% bootstrap CI: (-0.07778, 0.08696)
- sharpe 95% bootstrap CI: (-1.845, 2.288)
- rejection reasons: mean-return 95% bootstrap CI (-0.07778, 0.08696) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.845, 2.288) does not exclude zero (lower bound must be > 0)

## iron_condor / NVDA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3133
- profit_factor: 1.241
- sharpe: -0.207
- mean_return_pct: -0.00459
- total_pnl_dollars: 989.81
- max_drawdown_dollars: -875.93
- exit_reason_breakdown: {'stop_loss': 57, 'expiration': 26}
- mean-return 95% bootstrap CI: (-0.04885, 0.03682)
- sharpe 95% bootstrap CI: (-2.092, 1.847)
- rejection reasons: mean-return 95% bootstrap CI (-0.04885, 0.03682) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.092, 1.847) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / NVDA -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.6711
- profit_factor: 1.199
- sharpe: 0.243
- mean_return_pct: 0.00515
- total_pnl_dollars: 864.41
- max_drawdown_dollars: -1394.17
- exit_reason_breakdown: {'stop_loss': 3, 'time_exit': 73}
- mean-return 95% bootstrap CI: (-0.03543, 0.04486)
- sharpe 95% bootstrap CI: (-1.482, 2.865)
- rejection reasons: mean-return 95% bootstrap CI (-0.03543, 0.04486) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.482, 2.865) does not exclude zero (lower bound must be > 0)

## cash_secured_put / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4699
- profit_factor: 1.37
- sharpe: 1.42
- mean_return_pct: 0.00145
- total_pnl_dollars: 5675.38
- max_drawdown_dollars: -4025.89
- exit_reason_breakdown: {'stop_loss': 44, 'expiration': 39}
- mean-return 95% bootstrap CI: (-0.00052, 0.00347)
- sharpe 95% bootstrap CI: (-0.565, 3.223)
- rejection reasons: mean-return 95% bootstrap CI (-0.00052, 0.00347) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.565, 3.223) does not exclude zero (lower bound must be > 0)

## covered_call / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3253
- profit_factor: 1.267
- sharpe: 0.452
- mean_return_pct: 0.00039
- total_pnl_dollars: 2832.63
- max_drawdown_dollars: -2573.01
- exit_reason_breakdown: {'stop_loss': 56, 'expiration': 27}
- mean-return 95% bootstrap CI: (-0.00133, 0.00194)
- sharpe 95% bootstrap CI: (-1.271, 2.869)
- rejection reasons: mean-return 95% bootstrap CI (-0.00133, 0.00194) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.271, 2.869) does not exclude zero (lower bound must be > 0)

## long_directional / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.1566
- profit_factor: 0.534
- sharpe: -1.959
- mean_return_pct: -0.24879
- total_pnl_dollars: -14449.49
- max_drawdown_dollars: -18487.04
- exit_reason_breakdown: {'stop_loss': 68, 'expiration': 15}
- mean-return 95% bootstrap CI: (-0.47665, 0.02166)
- sharpe 95% bootstrap CI: (-5.858, 0.126)
- rejection reasons: mean-return 95% bootstrap CI (-0.47665, 0.02166) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-5.858, 0.126) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4458
- profit_factor: 1.075
- sharpe: -0.805
- mean_return_pct: -0.02947
- total_pnl_dollars: 771.23
- max_drawdown_dollars: -2847.21
- exit_reason_breakdown: {'stop_loss': 46, 'expiration': 37}
- mean-return 95% bootstrap CI: (-0.10215, 0.04164)
- sharpe 95% bootstrap CI: (-2.746, 1.212)
- rejection reasons: mean-return 95% bootstrap CI (-0.10215, 0.04164) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.746, 1.212) does not exclude zero (lower bound must be > 0)

## iron_condor / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4096
- profit_factor: 1.754
- sharpe: 1.099
- mean_return_pct: 0.03017
- total_pnl_dollars: 3961.4
- max_drawdown_dollars: -2320.88
- exit_reason_breakdown: {'stop_loss': 49, 'expiration': 34}
- mean-return 95% bootstrap CI: (-0.02548, 0.08006)
- sharpe 95% bootstrap CI: (-0.845, 3.321)
- rejection reasons: mean-return 95% bootstrap CI (-0.02548, 0.08006) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.845, 3.321) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / SPY -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5921
- profit_factor: 0.635
- sharpe: -2.191
- mean_return_pct: -0.07225
- total_pnl_dollars: -3640.3
- max_drawdown_dollars: -4794.01
- exit_reason_breakdown: {'time_exit': 66, 'stop_loss': 10}
- mean-return 95% bootstrap CI: (-0.13708, -0.00981)
- sharpe 95% bootstrap CI: (-3.855, -0.377)
- rejection reasons: mean-return 95% bootstrap CI (-0.13708, -0.00981) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.855, -0.377) does not exclude zero (lower bound must be > 0)

## cash_secured_put / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5181
- profit_factor: 1.423
- sharpe: 1.596
- mean_return_pct: 0.00209
- total_pnl_dollars: 7387.05
- max_drawdown_dollars: -4225.21
- exit_reason_breakdown: {'stop_loss': 40, 'expiration': 43}
- mean-return 95% bootstrap CI: (-0.00047, 0.00472)
- sharpe 95% bootstrap CI: (-0.383, 3.587)
- rejection reasons: mean-return 95% bootstrap CI (-0.00047, 0.00472) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.383, 3.587) does not exclude zero (lower bound must be > 0)

## covered_call / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4096
- profit_factor: 1.194
- sharpe: 0.26
- mean_return_pct: 0.0003
- total_pnl_dollars: 3244.55
- max_drawdown_dollars: -4805.98
- exit_reason_breakdown: {'stop_loss': 49, 'expiration': 34}
- mean-return 95% bootstrap CI: (-0.00194, 0.00258)
- sharpe 95% bootstrap CI: (-1.521, 2.679)
- rejection reasons: mean-return 95% bootstrap CI (-0.00194, 0.00258) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.521, 2.679) does not exclude zero (lower bound must be > 0)

## long_directional / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2169
- profit_factor: 0.953
- sharpe: 0.328
- mean_return_pct: 0.06769
- total_pnl_dollars: -2010.28
- max_drawdown_dollars: -14488.0
- exit_reason_breakdown: {'stop_loss': 56, 'expiration': 27}
- mean-return 95% bootstrap CI: (-0.32323, 0.47715)
- sharpe 95% bootstrap CI: (-2.159, 1.928)
- rejection reasons: mean-return 95% bootstrap CI (-0.32323, 0.47715) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.159, 1.928) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.494
- profit_factor: 1.114
- sharpe: 0.06
- mean_return_pct: 0.00218
- total_pnl_dollars: 1426.89
- max_drawdown_dollars: -3407.53
- exit_reason_breakdown: {'stop_loss': 42, 'expiration': 41}
- mean-return 95% bootstrap CI: (-0.07035, 0.07205)
- sharpe 95% bootstrap CI: (-1.868, 2.115)
- rejection reasons: mean-return 95% bootstrap CI (-0.07035, 0.07205) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.868, 2.115) does not exclude zero (lower bound must be > 0)

## iron_condor / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3133
- profit_factor: 1.207
- sharpe: -0.056
- mean_return_pct: -0.00135
- total_pnl_dollars: 1400.48
- max_drawdown_dollars: -2504.55
- exit_reason_breakdown: {'stop_loss': 57, 'expiration': 26}
- mean-return 95% bootstrap CI: (-0.04806, 0.04546)
- sharpe 95% bootstrap CI: (-1.936, 2.03)
- rejection reasons: mean-return 95% bootstrap CI (-0.04806, 0.04546) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.936, 2.03) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / QQQ -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5921
- profit_factor: 0.521
- sharpe: -2.65
- mean_return_pct: -0.09088
- total_pnl_dollars: -6676.37
- max_drawdown_dollars: -8083.47
- exit_reason_breakdown: {'time_exit': 63, 'stop_loss': 13}
- mean-return 95% bootstrap CI: (-0.15855, -0.02668)
- sharpe 95% bootstrap CI: (-4.286, -0.903)
- rejection reasons: mean-return 95% bootstrap CI (-0.15855, -0.02668) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.286, -0.903) does not exclude zero (lower bound must be > 0)

## cash_secured_put / AMD -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6867
- profit_factor: 1.529
- sharpe: 1.428
- mean_return_pct: 0.00786
- total_pnl_dollars: 12234.38
- max_drawdown_dollars: -7941.13
- exit_reason_breakdown: {'expiration': 69, 'stop_loss': 14}
- mean-return 95% bootstrap CI: (-0.00315, 0.01856)
- sharpe 95% bootstrap CI: (-0.511, 4.047)
- rejection reasons: mean-return 95% bootstrap CI (-0.00315, 0.01856) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.511, 4.047) does not exclude zero (lower bound must be > 0)

## covered_call / AMD -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6627
- profit_factor: 0.801
- sharpe: -1.363
- mean_return_pct: -0.00936
- total_pnl_dollars: -7584.1
- max_drawdown_dollars: -25002.69
- exit_reason_breakdown: {'expiration': 59, 'stop_loss': 24}
- mean-return 95% bootstrap CI: (-0.02345, 0.00335)
- sharpe 95% bootstrap CI: (-2.971, 0.622)
- rejection reasons: mean-return 95% bootstrap CI (-0.02345, 0.00335) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.971, 0.622) does not exclude zero (lower bound must be > 0)

## long_directional / AMD -- PASS (2026-09-01)

- trades: 83
- win_rate: 0.3133
- profit_factor: 1.822
- sharpe: 1.979
- mean_return_pct: 0.90757
- total_pnl_dollars: 41612.16
- max_drawdown_dollars: -17940.4
- exit_reason_breakdown: {'expiration': 59, 'stop_loss': 24}
- mean-return 95% bootstrap CI: (0.10198, 1.87993)
- sharpe 95% bootstrap CI: (0.368, 3.152)

## long_directional (extended history) / AMD -- PASS (2026-09-01)

- trades: 211
- win_rate: 0.3175
- profit_factor: 1.568
- sharpe: 2.387
- mean_return_pct: 0.51543
- total_pnl_dollars: 47735.55
- max_drawdown_dollars: -17940.4
- exit_reason_breakdown: {'expiration': 180, 'stop_loss': 31}
- mean-return 95% bootstrap CI: (0.11815, 0.96236)
- sharpe 95% bootstrap CI: (0.736, 3.695)

## long_directional (sub-period stability) / AMD -- FAIL (2026-09-01)

- trades: 105
- win_rate: 0.2857
- profit_factor: 0.997
- sharpe: 0.994
- mean_return_pct: 0.21741
- total_pnl_dollars: -75.67
- max_drawdown_dollars: -8208.58
- exit_reason_breakdown: {'expiration': 101, 'stop_loss': 4}
- mean-return 95% bootstrap CI: (-0.18497, 0.64592)
- sharpe 95% bootstrap CI: (-1.07, 2.567)
- rejection reasons: mean-return 95% bootstrap CI (-0.18497, 0.64592) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.07, 2.567) does not exclude zero (lower bound must be > 0)
- notes: second half: passed=True, sharpe=2.197

## vertical_credit_spread / AMD -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6386
- profit_factor: 1.505
- sharpe: 0.297
- mean_return_pct: 0.01702
- total_pnl_dollars: 6984.21
- max_drawdown_dollars: -5199.29
- exit_reason_breakdown: {'expiration': 69, 'stop_loss': 14}
- mean-return 95% bootstrap CI: (-0.09458, 0.12781)
- sharpe 95% bootstrap CI: (-1.503, 2.633)
- rejection reasons: mean-return 95% bootstrap CI (-0.09458, 0.12781) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.503, 2.633) does not exclude zero (lower bound must be > 0)

## iron_condor / AMD -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5904
- profit_factor: 1.301
- sharpe: -1.539
- mean_return_pct: -0.06662
- total_pnl_dollars: 4124.19
- max_drawdown_dollars: -3308.63
- exit_reason_breakdown: {'expiration': 57, 'stop_loss': 26}
- mean-return 95% bootstrap CI: (-0.15635, 0.01098)
- sharpe 95% bootstrap CI: (-3.305, 0.29)
- rejection reasons: mean-return 95% bootstrap CI (-0.15635, 0.01098) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.305, 0.29) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / AMD -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5263
- profit_factor: 0.485
- sharpe: -3.291
- mean_return_pct: -0.1033
- total_pnl_dollars: -8631.01
- max_drawdown_dollars: -11714.12
- exit_reason_breakdown: {'time_exit': 61, 'stop_loss': 15}
- mean-return 95% bootstrap CI: (-0.16357, -0.04243)
- sharpe 95% bootstrap CI: (-4.841, -1.561)
- rejection reasons: mean-return 95% bootstrap CI (-0.16357, -0.04243) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.841, -1.561) does not exclude zero (lower bound must be > 0)

## cash_secured_put / TSLA -- PASS (2026-09-01)

- trades: 83
- win_rate: 0.5301
- profit_factor: 1.63
- sharpe: 2.617
- mean_return_pct: 0.01146
- total_pnl_dollars: 18100.33
- max_drawdown_dollars: -5183.04
- exit_reason_breakdown: {'expiration': 44, 'stop_loss': 39}
- mean-return 95% bootstrap CI: (0.00288, 0.01965)
- sharpe 95% bootstrap CI: (0.603, 5.013)

## cash_secured_put (extended history) / TSLA -- FAIL (2026-09-01)

- trades: 211
- win_rate: 0.5308
- profit_factor: 1.187
- sharpe: 1.916
- mean_return_pct: 0.00556
- total_pnl_dollars: 14658.7
- max_drawdown_dollars: -16755.61
- exit_reason_breakdown: {'expiration': 113, 'stop_loss': 98}
- mean-return 95% bootstrap CI: (-1e-05, 0.01127)
- sharpe 95% bootstrap CI: (-0.004, 4.024)
- rejection reasons: mean-return 95% bootstrap CI (-1e-05, 0.01127) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.004, 4.024) does not exclude zero (lower bound must be > 0)

## covered_call / TSLA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4699
- profit_factor: 1.239
- sharpe: -0.317
- mean_return_pct: -0.00121
- total_pnl_dollars: 7119.71
- max_drawdown_dollars: -7456.41
- exit_reason_breakdown: {'stop_loss': 44, 'expiration': 39}
- mean-return 95% bootstrap CI: (-0.00921, 0.00593)
- sharpe 95% bootstrap CI: (-2.182, 1.877)
- rejection reasons: mean-return 95% bootstrap CI (-0.00921, 0.00593) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.182, 1.877) does not exclude zero (lower bound must be > 0)

## long_directional / TSLA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.1566
- profit_factor: 1.022
- sharpe: 0.467
- mean_return_pct: 0.11344
- total_pnl_dollars: 1721.88
- max_drawdown_dollars: -28299.97
- exit_reason_breakdown: {'stop_loss': 56, 'expiration': 27}
- mean-return 95% bootstrap CI: (-0.31508, 0.61321)
- sharpe 95% bootstrap CI: (-1.937, 2.015)
- rejection reasons: mean-return 95% bootstrap CI (-0.31508, 0.61321) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.937, 2.015) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / TSLA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5181
- profit_factor: 1.352
- sharpe: 1.311
- mean_return_pct: 0.05233
- total_pnl_dollars: 7032.85
- max_drawdown_dollars: -5048.01
- exit_reason_breakdown: {'expiration': 43, 'stop_loss': 40}
- mean-return 95% bootstrap CI: (-0.02735, 0.12838)
- sharpe 95% bootstrap CI: (-0.659, 3.549)
- rejection reasons: mean-return 95% bootstrap CI (-0.02735, 0.12838) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.659, 3.549) does not exclude zero (lower bound must be > 0)

## iron_condor / TSLA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3735
- profit_factor: 1.212
- sharpe: -0.528
- mean_return_pct: -0.01297
- total_pnl_dollars: 2872.2
- max_drawdown_dollars: -2953.62
- exit_reason_breakdown: {'stop_loss': 52, 'expiration': 31}
- mean-return 95% bootstrap CI: (-0.06112, 0.0369)
- sharpe 95% bootstrap CI: (-2.38, 1.63)
- rejection reasons: mean-return 95% bootstrap CI (-0.06112, 0.0369) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.38, 1.63) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / TSLA -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.6316
- profit_factor: 0.665
- sharpe: -2.048
- mean_return_pct: -0.05265
- total_pnl_dollars: -7148.03
- max_drawdown_dollars: -10663.03
- exit_reason_breakdown: {'time_exit': 68, 'stop_loss': 8}
- mean-return 95% bootstrap CI: (-0.10538, -0.00378)
- sharpe 95% bootstrap CI: (-3.726, -0.176)
- rejection reasons: mean-return 95% bootstrap CI (-0.10538, -0.00378) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.726, -0.176) does not exclude zero (lower bound must be > 0)

## cash_secured_put / AMZN -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5301
- profit_factor: 1.149
- sharpe: 0.824
- mean_return_pct: 0.00203
- total_pnl_dollars: 2287.29
- max_drawdown_dollars: -3010.77
- exit_reason_breakdown: {'stop_loss': 39, 'expiration': 44}
- mean-return 95% bootstrap CI: (-0.00297, 0.00693)
- sharpe 95% bootstrap CI: (-1.188, 3.027)
- rejection reasons: mean-return 95% bootstrap CI (-0.00297, 0.00693) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.188, 3.027) does not exclude zero (lower bound must be > 0)

## covered_call / AMZN -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4337
- profit_factor: 0.803
- sharpe: -1.12
- mean_return_pct: -0.00221
- total_pnl_dollars: -2978.07
- max_drawdown_dollars: -3578.51
- exit_reason_breakdown: {'expiration': 36, 'stop_loss': 47}
- mean-return 95% bootstrap CI: (-0.0063, 0.00161)
- sharpe 95% bootstrap CI: (-3.095, 0.894)
- rejection reasons: mean-return 95% bootstrap CI (-0.0063, 0.00161) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.095, 0.894) does not exclude zero (lower bound must be > 0)

## long_directional / AMZN -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.1807
- profit_factor: 0.533
- sharpe: -1.727
- mean_return_pct: -0.26761
- total_pnl_dollars: -13999.57
- max_drawdown_dollars: -13999.57
- exit_reason_breakdown: {'stop_loss': 60, 'expiration': 23}
- mean-return 95% bootstrap CI: (-0.54051, 0.04587)
- sharpe 95% bootstrap CI: (-5.148, 0.245)
- rejection reasons: mean-return 95% bootstrap CI (-0.54051, 0.04587) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-5.148, 0.245) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / AMZN -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.494
- profit_factor: 1.004
- sharpe: -0.751
- mean_return_pct: -0.03191
- total_pnl_dollars: 41.07
- max_drawdown_dollars: -2013.76
- exit_reason_breakdown: {'stop_loss': 42, 'expiration': 41}
- mean-return 95% bootstrap CI: (-0.11555, 0.04976)
- sharpe 95% bootstrap CI: (-2.63, 1.26)
- rejection reasons: mean-return 95% bootstrap CI (-0.11555, 0.04976) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.63, 1.26) does not exclude zero (lower bound must be > 0)

## iron_condor / AMZN -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3855
- profit_factor: 1.751
- sharpe: 0.474
- mean_return_pct: 0.01164
- total_pnl_dollars: 2799.43
- max_drawdown_dollars: -796.76
- exit_reason_breakdown: {'stop_loss': 51, 'expiration': 32}
- mean-return 95% bootstrap CI: (-0.03756, 0.05906)
- sharpe 95% bootstrap CI: (-1.467, 2.587)
- rejection reasons: mean-return 95% bootstrap CI (-0.03756, 0.05906) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.467, 2.587) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / AMZN -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.4868
- profit_factor: 0.367
- sharpe: -3.906
- mean_return_pct: -0.1302
- total_pnl_dollars: -6859.38
- max_drawdown_dollars: -6860.3
- exit_reason_breakdown: {'time_exit': 61, 'stop_loss': 15}
- mean-return 95% bootstrap CI: (-0.19776, -0.06693)
- sharpe 95% bootstrap CI: (-5.655, -2.236)
- rejection reasons: mean-return 95% bootstrap CI (-0.19776, -0.06693) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-5.655, -2.236) does not exclude zero (lower bound must be > 0)

## cash_secured_put / GOOGL -- PASS (2026-09-01)

- trades: 83
- win_rate: 0.6145
- profit_factor: 1.659
- sharpe: 2.605
- mean_return_pct: 0.005
- total_pnl_dollars: 7183.72
- max_drawdown_dollars: -2554.56
- exit_reason_breakdown: {'expiration': 52, 'stop_loss': 31}
- mean-return 95% bootstrap CI: (0.0012, 0.00885)
- sharpe 95% bootstrap CI: (0.594, 5.075)

## cash_secured_put (extended history) / GOOGL -- PASS (2026-09-01)

- trades: 211
- win_rate: 0.6967
- profit_factor: 1.55
- sharpe: 3.471
- mean_return_pct: 0.00514
- total_pnl_dollars: 12777.61
- max_drawdown_dollars: -4092.37
- exit_reason_breakdown: {'expiration': 152, 'stop_loss': 59}
- mean-return 95% bootstrap CI: (0.00222, 0.00795)
- sharpe 95% bootstrap CI: (1.43, 5.939)

## cash_secured_put (sub-period stability) / GOOGL -- PASS (2026-09-01)

- trades: 105
- win_rate: 0.7619
- profit_factor: 1.631
- sharpe: 2.781
- mean_return_pct: 0.00631
- total_pnl_dollars: 5662.67
- max_drawdown_dollars: -4092.37
- exit_reason_breakdown: {'expiration': 84, 'stop_loss': 21}
- mean-return 95% bootstrap CI: (0.00187, 0.01084)
- sharpe 95% bootstrap CI: (0.752, 5.656)
- notes: second half: passed=True, sharpe=2.094

## covered_call / GOOGL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3976
- profit_factor: 0.709
- sharpe: -1.581
- mean_return_pct: -0.00338
- total_pnl_dollars: -4777.54
- max_drawdown_dollars: -5963.62
- exit_reason_breakdown: {'stop_loss': 49, 'expiration': 34}
- mean-return 95% bootstrap CI: (-0.00769, 0.00071)
- sharpe 95% bootstrap CI: (-3.465, 0.391)
- rejection reasons: mean-return 95% bootstrap CI (-0.00769, 0.00071) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.465, 0.391) does not exclude zero (lower bound must be > 0)

## long_directional / GOOGL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2771
- profit_factor: 1.515
- sharpe: 1.622
- mean_return_pct: 0.46524
- total_pnl_dollars: 13515.51
- max_drawdown_dollars: -7368.85
- exit_reason_breakdown: {'stop_loss': 43, 'expiration': 40}
- mean-return 95% bootstrap CI: (-0.05261, 1.09138)
- sharpe 95% bootstrap CI: (-0.269, 3.16)
- rejection reasons: mean-return 95% bootstrap CI (-0.05261, 1.09138) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.269, 3.16) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / GOOGL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6024
- profit_factor: 1.372
- sharpe: 1.498
- mean_return_pct: 0.05757
- total_pnl_dollars: 2742.46
- max_drawdown_dollars: -1769.21
- exit_reason_breakdown: {'expiration': 51, 'stop_loss': 32}
- mean-return 95% bootstrap CI: (-0.02146, 0.13478)
- sharpe 95% bootstrap CI: (-0.507, 4.001)
- rejection reasons: mean-return 95% bootstrap CI (-0.02146, 0.13478) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.507, 4.001) does not exclude zero (lower bound must be > 0)

## iron_condor / GOOGL -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3614
- profit_factor: 1.153
- sharpe: -1.133
- mean_return_pct: -0.03331
- total_pnl_dollars: 889.24
- max_drawdown_dollars: -1277.69
- exit_reason_breakdown: {'stop_loss': 53, 'expiration': 30}
- mean-return 95% bootstrap CI: (-0.09005, 0.02294)
- sharpe 95% bootstrap CI: (-2.979, 0.853)
- rejection reasons: mean-return 95% bootstrap CI (-0.09005, 0.02294) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.979, 0.853) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / GOOGL -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.4474
- profit_factor: 0.314
- sharpe: -4.048
- mean_return_pct: -0.14003
- total_pnl_dollars: -7722.88
- max_drawdown_dollars: -8222.7
- exit_reason_breakdown: {'time_exit': 62, 'stop_loss': 14}
- mean-return 95% bootstrap CI: (-0.20891, -0.07427)
- sharpe 95% bootstrap CI: (-5.816, -2.388)
- rejection reasons: mean-return 95% bootstrap CI (-0.20891, -0.07427) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-5.816, -2.388) does not exclude zero (lower bound must be > 0)

## cash_secured_put / META -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5422
- profit_factor: 1.148
- sharpe: 0.915
- mean_return_pct: 0.00271
- total_pnl_dollars: 7327.58
- max_drawdown_dollars: -13460.9
- exit_reason_breakdown: {'stop_loss': 38, 'expiration': 45}
- mean-return 95% bootstrap CI: (-0.00302, 0.00835)
- sharpe 95% bootstrap CI: (-0.934, 3.15)
- rejection reasons: mean-return 95% bootstrap CI (-0.00302, 0.00835) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.934, 3.15) does not exclude zero (lower bound must be > 0)

## covered_call / META -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4337
- profit_factor: 0.789
- sharpe: -0.997
- mean_return_pct: -0.00259
- total_pnl_dollars: -10567.44
- max_drawdown_dollars: -22399.37
- exit_reason_breakdown: {'expiration': 36, 'stop_loss': 47}
- mean-return 95% bootstrap CI: (-0.00797, 0.00244)
- sharpe 95% bootstrap CI: (-2.652, 1.132)
- rejection reasons: mean-return 95% bootstrap CI (-0.00797, 0.00244) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.652, 1.132) does not exclude zero (lower bound must be > 0)

## long_directional / META -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.0843
- profit_factor: 0.212
- sharpe: -4.671
- mean_return_pct: -0.54117
- total_pnl_dollars: -80490.38
- max_drawdown_dollars: -80490.38
- exit_reason_breakdown: {'stop_loss': 67, 'expiration': 16}
- mean-return 95% bootstrap CI: (-0.74854, -0.2816)
- sharpe 95% bootstrap CI: (-13.641, -1.77)
- rejection reasons: mean-return 95% bootstrap CI (-0.74854, -0.2816) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-13.641, -1.77) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / META -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.506
- profit_factor: 1.055
- sharpe: -0.735
- mean_return_pct: -0.03396
- total_pnl_dollars: 1624.64
- max_drawdown_dollars: -8952.93
- exit_reason_breakdown: {'stop_loss': 41, 'expiration': 42}
- mean-return 95% bootstrap CI: (-0.124, 0.05566)
- sharpe 95% bootstrap CI: (-2.591, 1.322)
- rejection reasons: mean-return 95% bootstrap CI (-0.124, 0.05566) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.591, 1.322) does not exclude zero (lower bound must be > 0)

## iron_condor / META -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3855
- profit_factor: 1.257
- sharpe: -0.989
- mean_return_pct: -0.02984
- total_pnl_dollars: 4441.72
- max_drawdown_dollars: -3177.78
- exit_reason_breakdown: {'stop_loss': 51, 'expiration': 32}
- mean-return 95% bootstrap CI: (-0.0905, 0.0263)
- sharpe 95% bootstrap CI: (-2.854, 0.977)
- rejection reasons: mean-return 95% bootstrap CI (-0.0905, 0.0263) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.854, 0.977) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / META -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5658
- profit_factor: 0.529
- sharpe: -2.578
- mean_return_pct: -0.0797
- total_pnl_dollars: -12152.28
- max_drawdown_dollars: -13301.32
- exit_reason_breakdown: {'time_exit': 64, 'stop_loss': 12}
- mean-return 95% bootstrap CI: (-0.14056, -0.02066)
- sharpe 95% bootstrap CI: (-4.132, -0.851)
- rejection reasons: mean-return 95% bootstrap CI (-0.14056, -0.02066) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.132, -0.851) does not exclude zero (lower bound must be > 0)

## cash_secured_put / JPM -- PASS (2026-09-01)

- trades: 83
- win_rate: 0.6265
- profit_factor: 1.82
- sharpe: 2.438
- mean_return_pct: 0.0041
- total_pnl_dollars: 8355.39
- max_drawdown_dollars: -2939.06
- exit_reason_breakdown: {'expiration': 52, 'stop_loss': 31}
- mean-return 95% bootstrap CI: (0.00087, 0.00732)
- sharpe 95% bootstrap CI: (0.493, 4.81)

## cash_secured_put (extended history) / JPM -- PASS (2026-09-01)

- trades: 211
- win_rate: 0.673
- profit_factor: 1.389
- sharpe: 2.093
- mean_return_pct: 0.00273
- total_pnl_dollars: 9717.0
- max_drawdown_dollars: -4055.05
- exit_reason_breakdown: {'expiration': 144, 'stop_loss': 67}
- mean-return 95% bootstrap CI: (0.00014, 0.00535)
- sharpe 95% bootstrap CI: (0.095, 4.479)

## cash_secured_put (sub-period stability) / JPM -- FAIL (2026-09-01)

- trades: 105
- win_rate: 0.6857
- profit_factor: 1.216
- sharpe: 1.335
- mean_return_pct: 0.00273
- total_pnl_dollars: 2487.34
- max_drawdown_dollars: -4055.05
- exit_reason_breakdown: {'expiration': 73, 'stop_loss': 32}
- mean-return 95% bootstrap CI: (-0.00153, 0.00658)
- sharpe 95% bootstrap CI: (-0.699, 3.636)
- rejection reasons: mean-return 95% bootstrap CI (-0.00153, 0.00658) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.699, 3.636) does not exclude zero (lower bound must be > 0)
- notes: second half: passed=False, sharpe=1.678

## covered_call / JPM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3373
- profit_factor: 0.701
- sharpe: -1.427
- mean_return_pct: -0.00247
- total_pnl_dollars: -3894.38
- max_drawdown_dollars: -5299.23
- exit_reason_breakdown: {'stop_loss': 55, 'expiration': 28}
- mean-return 95% bootstrap CI: (-0.00607, 0.00068)
- sharpe 95% bootstrap CI: (-2.976, 0.527)
- rejection reasons: mean-return 95% bootstrap CI (-0.00607, 0.00068) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.976, 0.527) does not exclude zero (lower bound must be > 0)

## long_directional / JPM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.1928
- profit_factor: 0.643
- sharpe: -1.034
- mean_return_pct: -0.17053
- total_pnl_dollars: -9281.47
- max_drawdown_dollars: -11973.7
- exit_reason_breakdown: {'stop_loss': 62, 'expiration': 21}
- mean-return 95% bootstrap CI: (-0.45403, 0.16617)
- sharpe 95% bootstrap CI: (-4.014, 0.816)
- rejection reasons: mean-return 95% bootstrap CI (-0.45403, 0.16617) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.014, 0.816) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / JPM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6265
- profit_factor: 1.544
- sharpe: 1.08
- mean_return_pct: 0.04355
- total_pnl_dollars: 3807.71
- max_drawdown_dollars: -2102.56
- exit_reason_breakdown: {'expiration': 52, 'stop_loss': 31}
- mean-return 95% bootstrap CI: (-0.03507, 0.12047)
- sharpe 95% bootstrap CI: (-0.79, 3.462)
- rejection reasons: mean-return 95% bootstrap CI (-0.03507, 0.12047) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.79, 3.462) does not exclude zero (lower bound must be > 0)

## iron_condor / JPM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3494
- profit_factor: 1.593
- sharpe: 0.182
- mean_return_pct: 0.00481
- total_pnl_dollars: 2198.8
- max_drawdown_dollars: -1127.09
- exit_reason_breakdown: {'stop_loss': 54, 'expiration': 29}
- mean-return 95% bootstrap CI: (-0.04948, 0.05288)
- sharpe 95% bootstrap CI: (-1.726, 2.258)
- rejection reasons: mean-return 95% bootstrap CI (-0.04948, 0.05288) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.726, 2.258) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / JPM -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5526
- profit_factor: 0.558
- sharpe: -2.152
- mean_return_pct: -0.05986
- total_pnl_dollars: -3000.04
- max_drawdown_dollars: -3450.87
- exit_reason_breakdown: {'time_exit': 70, 'stop_loss': 6}
- mean-return 95% bootstrap CI: (-0.11574, -0.0061)
- sharpe 95% bootstrap CI: (-3.769, -0.267)
- rejection reasons: mean-return 95% bootstrap CI (-0.11574, -0.0061) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.769, -0.267) does not exclude zero (lower bound must be > 0)

## cash_secured_put / BAC -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6386
- profit_factor: 1.53
- sharpe: 1.825
- mean_return_pct: 0.00349
- total_pnl_dollars: 1131.25
- max_drawdown_dollars: -782.58
- exit_reason_breakdown: {'expiration': 53, 'stop_loss': 30}
- mean-return 95% bootstrap CI: (-0.00034, 0.00716)
- sharpe 95% bootstrap CI: (-0.16, 4.374)
- rejection reasons: mean-return 95% bootstrap CI (-0.00034, 0.00716) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.16, 4.374) does not exclude zero (lower bound must be > 0)

## covered_call / BAC -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3976
- profit_factor: 0.706
- sharpe: -1.447
- mean_return_pct: -0.00225
- total_pnl_dollars: -776.96
- max_drawdown_dollars: -828.97
- exit_reason_breakdown: {'stop_loss': 50, 'expiration': 33}
- mean-return 95% bootstrap CI: (-0.00535, 0.00069)
- sharpe 95% bootstrap CI: (-3.348, 0.477)
- rejection reasons: mean-return 95% bootstrap CI (-0.00535, 0.00069) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.348, 0.477) does not exclude zero (lower bound must be > 0)

## long_directional / BAC -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2289
- profit_factor: 0.869
- sharpe: -0.853
- mean_return_pct: -0.13468
- total_pnl_dollars: -595.53
- max_drawdown_dollars: -1875.1
- exit_reason_breakdown: {'stop_loss': 49, 'expiration': 34}
- mean-return 95% bootstrap CI: (-0.41771, 0.18857)
- sharpe 95% bootstrap CI: (-3.296, 1.05)
- rejection reasons: mean-return 95% bootstrap CI (-0.41771, 0.18857) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.296, 1.05) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / BAC -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6265
- profit_factor: 1.398
- sharpe: 1.126
- mean_return_pct: 0.04596
- total_pnl_dollars: 534.72
- max_drawdown_dollars: -432.86
- exit_reason_breakdown: {'expiration': 52, 'stop_loss': 31}
- mean-return 95% bootstrap CI: (-0.03625, 0.12359)
- sharpe 95% bootstrap CI: (-0.82, 3.52)
- rejection reasons: mean-return 95% bootstrap CI (-0.03625, 0.12359) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.82, 3.52) does not exclude zero (lower bound must be > 0)

## iron_condor / BAC -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3373
- profit_factor: 1.391
- sharpe: 0.341
- mean_return_pct: 0.00784
- total_pnl_dollars: 258.93
- max_drawdown_dollars: -135.31
- exit_reason_breakdown: {'stop_loss': 55, 'expiration': 28}
- mean-return 95% bootstrap CI: (-0.03778, 0.05362)
- sharpe 95% bootstrap CI: (-1.614, 2.374)
- rejection reasons: mean-return 95% bootstrap CI (-0.03778, 0.05362) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.614, 2.374) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / BAC -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.4605
- profit_factor: 0.347
- sharpe: -3.911
- mean_return_pct: -0.13689
- total_pnl_dollars: -1200.76
- max_drawdown_dollars: -1233.97
- exit_reason_breakdown: {'time_exit': 60, 'stop_loss': 16}
- mean-return 95% bootstrap CI: (-0.20455, -0.07015)
- sharpe 95% bootstrap CI: (-5.546, -2.245)
- rejection reasons: mean-return 95% bootstrap CI (-0.20455, -0.07015) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-5.546, -2.245) does not exclude zero (lower bound must be > 0)

## cash_secured_put / WMT -- PASS (2026-09-01)

- trades: 83
- win_rate: 0.7229
- profit_factor: 1.721
- sharpe: 2.661
- mean_return_pct: 0.00423
- total_pnl_dollars: 2659.47
- max_drawdown_dollars: -1344.26
- exit_reason_breakdown: {'expiration': 62, 'stop_loss': 21}
- mean-return 95% bootstrap CI: (0.00104, 0.00724)
- sharpe 95% bootstrap CI: (0.594, 5.442)

## cash_secured_put (extended history) / WMT -- FAIL (2026-09-01)

- trades: 211
- win_rate: 0.763
- profit_factor: 1.313
- sharpe: 1.398
- mean_return_pct: 0.00208
- total_pnl_dollars: 2700.95
- max_drawdown_dollars: -2515.18
- exit_reason_breakdown: {'expiration': 181, 'stop_loss': 30}
- mean-return 95% bootstrap CI: (-0.00085, 0.00481)
- sharpe 95% bootstrap CI: (-0.471, 4.047)
- rejection reasons: mean-return 95% bootstrap CI (-0.00085, 0.00481) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.471, 4.047) does not exclude zero (lower bound must be > 0)

## covered_call / WMT -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4337
- profit_factor: 0.621
- sharpe: -2.381
- mean_return_pct: -0.00455
- total_pnl_dollars: -2681.54
- max_drawdown_dollars: -3681.83
- exit_reason_breakdown: {'expiration': 37, 'stop_loss': 46}
- mean-return 95% bootstrap CI: (-0.00817, -0.00094)
- sharpe 95% bootstrap CI: (-4.201, -0.56)
- rejection reasons: mean-return 95% bootstrap CI (-0.00817, -0.00094) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.201, -0.56) does not exclude zero (lower bound must be > 0)

## long_directional / WMT -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2289
- profit_factor: 0.973
- sharpe: 1.202
- mean_return_pct: 0.3637
- total_pnl_dollars: -258.63
- max_drawdown_dollars: -4621.11
- exit_reason_breakdown: {'expiration': 40, 'stop_loss': 43}
- mean-return 95% bootstrap CI: (-0.16692, 1.01835)
- sharpe 95% bootstrap CI: (-0.732, 2.719)
- rejection reasons: mean-return 95% bootstrap CI (-0.16692, 1.01835) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.732, 2.719) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / WMT -- PASS (2026-09-01)

- trades: 83
- win_rate: 0.6747
- profit_factor: 1.43
- sharpe: 2.086
- mean_return_pct: 0.08087
- total_pnl_dollars: 1055.94
- max_drawdown_dollars: -926.14
- exit_reason_breakdown: {'expiration': 59, 'stop_loss': 24}
- mean-return 95% bootstrap CI: (0.0024, 0.1548)
- sharpe 95% bootstrap CI: (0.054, 4.773)

## vertical_credit_spread (extended history) / WMT -- FAIL (2026-09-01)

- trades: 211
- win_rate: 0.7393
- profit_factor: 1.407
- sharpe: 1.826
- mean_return_pct: 0.05637
- total_pnl_dollars: 1853.47
- max_drawdown_dollars: -926.14
- exit_reason_breakdown: {'expiration': 178, 'stop_loss': 33}
- mean-return 95% bootstrap CI: (-0.00484, 0.11515)
- sharpe 95% bootstrap CI: (-0.143, 4.175)
- rejection reasons: mean-return 95% bootstrap CI (-0.00484, 0.11515) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.143, 4.175) does not exclude zero (lower bound must be > 0)

## iron_condor / WMT -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4217
- profit_factor: 1.105
- sharpe: -1.558
- mean_return_pct: -0.05765
- total_pnl_dollars: 223.3
- max_drawdown_dollars: -549.69
- exit_reason_breakdown: {'expiration': 35, 'stop_loss': 48}
- mean-return 95% bootstrap CI: (-0.12924, 0.01257)
- sharpe 95% bootstrap CI: (-3.379, 0.392)
- rejection reasons: mean-return 95% bootstrap CI (-0.12924, 0.01257) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.379, 0.392) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / WMT -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5
- profit_factor: 0.41
- sharpe: -3.742
- mean_return_pct: -0.13139
- total_pnl_dollars: -2042.42
- max_drawdown_dollars: -2115.32
- exit_reason_breakdown: {'time_exit': 59, 'stop_loss': 17}
- mean-return 95% bootstrap CI: (-0.20092, -0.06408)
- sharpe 95% bootstrap CI: (-5.432, -2.078)
- rejection reasons: mean-return 95% bootstrap CI (-0.20092, -0.06408) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-5.432, -2.078) does not exclude zero (lower bound must be > 0)

## cash_secured_put / UNH -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.494
- profit_factor: 0.831
- sharpe: -0.139
- mean_return_pct: -0.00056
- total_pnl_dollars: -7486.1
- max_drawdown_dollars: -21026.33
- exit_reason_breakdown: {'expiration': 41, 'stop_loss': 42}
- mean-return 95% bootstrap CI: (-0.00891, 0.00667)
- sharpe 95% bootstrap CI: (-1.912, 2.011)
- rejection reasons: mean-return 95% bootstrap CI (-0.00891, 0.00667) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.912, 2.011) does not exclude zero (lower bound must be > 0)

## covered_call / UNH -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4217
- profit_factor: 1.393
- sharpe: 0.866
- mean_return_pct: 0.00211
- total_pnl_dollars: 8545.49
- max_drawdown_dollars: -6363.73
- exit_reason_breakdown: {'stop_loss': 48, 'expiration': 35}
- mean-return 95% bootstrap CI: (-0.00287, 0.00677)
- sharpe 95% bootstrap CI: (-1.116, 3.089)
- rejection reasons: mean-return 95% bootstrap CI (-0.00287, 0.00677) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.116, 3.089) does not exclude zero (lower bound must be > 0)

## long_directional / UNH -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.1446
- profit_factor: 0.823
- sharpe: -1.097
- mean_return_pct: -0.16289
- total_pnl_dollars: -8156.01
- max_drawdown_dollars: -17428.78
- exit_reason_breakdown: {'stop_loss': 71, 'expiration': 12}
- mean-return 95% bootstrap CI: (-0.42544, 0.15842)
- sharpe 95% bootstrap CI: (-4.778, 0.824)
- rejection reasons: mean-return 95% bootstrap CI (-0.42544, 0.15842) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.778, 0.824) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / UNH -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4699
- profit_factor: 1.133
- sharpe: -0.449
- mean_return_pct: -0.0197
- total_pnl_dollars: 2377.61
- max_drawdown_dollars: -6455.18
- exit_reason_breakdown: {'expiration': 39, 'stop_loss': 44}
- mean-return 95% bootstrap CI: (-0.10808, 0.0654)
- sharpe 95% bootstrap CI: (-2.232, 1.642)
- rejection reasons: mean-return 95% bootstrap CI (-0.10808, 0.0654) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.232, 1.642) does not exclude zero (lower bound must be > 0)

## iron_condor / UNH -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3373
- profit_factor: 1.263
- sharpe: -0.016
- mean_return_pct: -0.00038
- total_pnl_dollars: 2730.71
- max_drawdown_dollars: -4323.36
- exit_reason_breakdown: {'stop_loss': 55, 'expiration': 28}
- mean-return 95% bootstrap CI: (-0.05019, 0.04797)
- sharpe 95% bootstrap CI: (-1.925, 2.178)
- rejection reasons: mean-return 95% bootstrap CI (-0.05019, 0.04797) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.925, 2.178) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / UNH -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.4737
- profit_factor: 0.321
- sharpe: -4.053
- mean_return_pct: -0.13475
- total_pnl_dollars: -18368.45
- max_drawdown_dollars: -18890.91
- exit_reason_breakdown: {'time_exit': 58, 'stop_loss': 18}
- mean-return 95% bootstrap CI: (-0.19555, -0.07236)
- sharpe 95% bootstrap CI: (-5.618, -2.43)
- rejection reasons: mean-return 95% bootstrap CI (-0.19555, -0.07236) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-5.618, -2.43) does not exclude zero (lower bound must be > 0)

## cash_secured_put / V -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5422
- profit_factor: 1.059
- sharpe: 0.34
- mean_return_pct: 0.00056
- total_pnl_dollars: 916.87
- max_drawdown_dollars: -4619.32
- exit_reason_breakdown: {'expiration': 45, 'stop_loss': 38}
- mean-return 95% bootstrap CI: (-0.00277, 0.00375)
- sharpe 95% bootstrap CI: (-1.567, 2.667)
- rejection reasons: mean-return 95% bootstrap CI (-0.00277, 0.00375) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.567, 2.667) does not exclude zero (lower bound must be > 0)

## covered_call / V -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.506
- profit_factor: 1.405
- sharpe: 1.097
- mean_return_pct: 0.00139
- total_pnl_dollars: 4249.75
- max_drawdown_dollars: -2259.18
- exit_reason_breakdown: {'stop_loss': 41, 'expiration': 42}
- mean-return 95% bootstrap CI: (-0.00119, 0.00383)
- sharpe 95% bootstrap CI: (-0.853, 3.539)
- rejection reasons: mean-return 95% bootstrap CI (-0.00119, 0.00383) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.853, 3.539) does not exclude zero (lower bound must be > 0)

## long_directional / V -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.1928
- profit_factor: 0.615
- sharpe: -1.172
- mean_return_pct: -0.18831
- total_pnl_dollars: -10477.25
- max_drawdown_dollars: -15916.57
- exit_reason_breakdown: {'stop_loss': 52, 'expiration': 31}
- mean-return 95% bootstrap CI: (-0.47015, 0.13831)
- sharpe 95% bootstrap CI: (-4.412, 0.727)
- rejection reasons: mean-return 95% bootstrap CI (-0.47015, 0.13831) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.412, 0.727) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / V -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5422
- profit_factor: 1.066
- sharpe: -0.318
- mean_return_pct: -0.01345
- total_pnl_dollars: 597.43
- max_drawdown_dollars: -3074.25
- exit_reason_breakdown: {'expiration': 45, 'stop_loss': 38}
- mean-return 95% bootstrap CI: (-0.0979, 0.0708)
- sharpe 95% bootstrap CI: (-2.198, 1.839)
- rejection reasons: mean-return 95% bootstrap CI (-0.0979, 0.0708) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.198, 1.839) does not exclude zero (lower bound must be > 0)

## iron_condor / V -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3976
- profit_factor: 1.236
- sharpe: -0.533
- mean_return_pct: -0.01603
- total_pnl_dollars: 1312.02
- max_drawdown_dollars: -1677.53
- exit_reason_breakdown: {'expiration': 33, 'stop_loss': 50}
- mean-return 95% bootstrap CI: (-0.07663, 0.04212)
- sharpe 95% bootstrap CI: (-2.45, 1.532)
- rejection reasons: mean-return 95% bootstrap CI (-0.07663, 0.04212) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.45, 1.532) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / V -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.6579
- profit_factor: 0.99
- sharpe: -0.714
- mean_return_pct: -0.01973
- total_pnl_dollars: -49.52
- max_drawdown_dollars: -1933.02
- exit_reason_breakdown: {'time_exit': 71, 'stop_loss': 5}
- mean-return 95% bootstrap CI: (-0.07899, 0.03179)
- sharpe 95% bootstrap CI: (-2.454, 1.468)
- rejection reasons: mean-return 95% bootstrap CI (-0.07899, 0.03179) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.454, 1.468) does not exclude zero (lower bound must be > 0)

## cash_secured_put / XOM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6506
- profit_factor: 1.484
- sharpe: 1.803
- mean_return_pct: 0.0031
- total_pnl_dollars: 2707.68
- max_drawdown_dollars: -1285.48
- exit_reason_breakdown: {'expiration': 56, 'stop_loss': 27}
- mean-return 95% bootstrap CI: (-0.0005, 0.00632)
- sharpe 95% bootstrap CI: (-0.256, 4.281)
- rejection reasons: mean-return 95% bootstrap CI (-0.0005, 0.00632) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.256, 4.281) does not exclude zero (lower bound must be > 0)

## covered_call / XOM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5663
- profit_factor: 1.346
- sharpe: 1.167
- mean_return_pct: 0.00162
- total_pnl_dollars: 1725.34
- max_drawdown_dollars: -1410.46
- exit_reason_breakdown: {'expiration': 47, 'stop_loss': 36}
- mean-return 95% bootstrap CI: (-0.00112, 0.00416)
- sharpe 95% bootstrap CI: (-0.8, 3.267)
- rejection reasons: mean-return 95% bootstrap CI (-0.00112, 0.00416) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.8, 3.267) does not exclude zero (lower bound must be > 0)

## long_directional / XOM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.1928
- profit_factor: 0.748
- sharpe: -0.804
- mean_return_pct: -0.16573
- total_pnl_dollars: -3398.9
- max_drawdown_dollars: -7402.49
- exit_reason_breakdown: {'expiration': 43, 'stop_loss': 40}
- mean-return 95% bootstrap CI: (-0.51125, 0.28027)
- sharpe 95% bootstrap CI: (-3.809, 1.055)
- rejection reasons: mean-return 95% bootstrap CI (-0.51125, 0.28027) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.809, 1.055) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / XOM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.6506
- profit_factor: 1.361
- sharpe: 1.328
- mean_return_pct: 0.05396
- total_pnl_dollars: 1297.66
- max_drawdown_dollars: -840.74
- exit_reason_breakdown: {'expiration': 56, 'stop_loss': 27}
- mean-return 95% bootstrap CI: (-0.02998, 0.13194)
- sharpe 95% bootstrap CI: (-0.681, 3.84)
- rejection reasons: mean-return 95% bootstrap CI (-0.02998, 0.13194) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.681, 3.84) does not exclude zero (lower bound must be > 0)

## iron_condor / XOM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4217
- profit_factor: 1.573
- sharpe: 1.123
- mean_return_pct: 0.02774
- total_pnl_dollars: 994.37
- max_drawdown_dollars: -291.19
- exit_reason_breakdown: {'expiration': 35, 'stop_loss': 48}
- mean-return 95% bootstrap CI: (-0.0234, 0.07252)
- sharpe 95% bootstrap CI: (-0.929, 3.106)
- rejection reasons: mean-return 95% bootstrap CI (-0.0234, 0.07252) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.929, 3.106) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / XOM -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.6316
- profit_factor: 0.7
- sharpe: -1.007
- mean_return_pct: -0.0277
- total_pnl_dollars: -829.22
- max_drawdown_dollars: -1305.89
- exit_reason_breakdown: {'time_exit': 69, 'stop_loss': 7}
- mean-return 95% bootstrap CI: (-0.08087, 0.02446)
- sharpe 95% bootstrap CI: (-2.563, 1.102)
- rejection reasons: mean-return 95% bootstrap CI (-0.08087, 0.02446) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.563, 1.102) does not exclude zero (lower bound must be > 0)

## cash_secured_put / IWM -- PASS (2026-09-01)

- trades: 83
- win_rate: 0.506
- profit_factor: 1.566
- sharpe: 1.901
- mean_return_pct: 0.00251
- total_pnl_dollars: 4226.74
- max_drawdown_dollars: -3338.42
- exit_reason_breakdown: {'expiration': 42, 'stop_loss': 41}
- mean-return 95% bootstrap CI: (7e-05, 0.00504)
- sharpe 95% bootstrap CI: (0.054, 4.071)

## cash_secured_put (extended history) / IWM -- PASS (2026-09-01)

- trades: 211
- win_rate: 0.4739
- profit_factor: 1.491
- sharpe: 2.898
- mean_return_pct: 0.00234
- total_pnl_dollars: 8653.94
- max_drawdown_dollars: -3338.42
- exit_reason_breakdown: {'stop_loss': 111, 'expiration': 100}
- mean-return 95% bootstrap CI: (0.00077, 0.00391)
- sharpe 95% bootstrap CI: (0.945, 4.926)

## cash_secured_put (sub-period stability) / IWM -- FAIL (2026-09-01)

- trades: 105
- win_rate: 0.4286
- profit_factor: 1.349
- sharpe: 1.714
- mean_return_pct: 0.00193
- total_pnl_dollars: 2962.77
- max_drawdown_dollars: -1787.2
- exit_reason_breakdown: {'stop_loss': 60, 'expiration': 45}
- mean-return 95% bootstrap CI: (-0.00029, 0.00401)
- sharpe 95% bootstrap CI: (-0.268, 3.611)
- rejection reasons: mean-return 95% bootstrap CI (-0.00029, 0.00401) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.268, 3.611) does not exclude zero (lower bound must be > 0)
- notes: second half: passed=True, sharpe=2.375

## covered_call / IWM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3976
- profit_factor: 1.175
- sharpe: 0.259
- mean_return_pct: 0.00031
- total_pnl_dollars: 1226.23
- max_drawdown_dollars: -2512.13
- exit_reason_breakdown: {'stop_loss': 50, 'expiration': 33}
- mean-return 95% bootstrap CI: (-0.00205, 0.00243)
- sharpe 95% bootstrap CI: (-1.531, 2.542)
- rejection reasons: mean-return 95% bootstrap CI (-0.00205, 0.00243) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.531, 2.542) does not exclude zero (lower bound must be > 0)

## long_directional / IWM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.0964
- profit_factor: 0.464
- sharpe: -2.049
- mean_return_pct: -0.29376
- total_pnl_dollars: -10159.48
- max_drawdown_dollars: -10159.48
- exit_reason_breakdown: {'stop_loss': 72, 'expiration': 11}
- mean-return 95% bootstrap CI: (-0.55488, 0.01402)
- sharpe 95% bootstrap CI: (-7.278, 0.071)
- rejection reasons: mean-return 95% bootstrap CI (-0.55488, 0.01402) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-7.278, 0.071) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / IWM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.494
- profit_factor: 1.349
- sharpe: 0.615
- mean_return_pct: 0.0208
- total_pnl_dollars: 1744.85
- max_drawdown_dollars: -1787.2
- exit_reason_breakdown: {'expiration': 41, 'stop_loss': 42}
- mean-return 95% bootstrap CI: (-0.0415, 0.08371)
- sharpe 95% bootstrap CI: (-1.201, 2.694)
- rejection reasons: mean-return 95% bootstrap CI (-0.0415, 0.08371) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.201, 2.694) does not exclude zero (lower bound must be > 0)

## iron_condor / IWM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3735
- profit_factor: 1.419
- sharpe: 0.236
- mean_return_pct: 0.00619
- total_pnl_dollars: 1320.24
- max_drawdown_dollars: -1222.76
- exit_reason_breakdown: {'stop_loss': 52, 'expiration': 31}
- mean-return 95% bootstrap CI: (-0.04421, 0.05734)
- sharpe 95% bootstrap CI: (-1.621, 2.381)
- rejection reasons: mean-return 95% bootstrap CI (-0.04421, 0.05734) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.621, 2.381) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / IWM -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5921
- profit_factor: 0.551
- sharpe: -2.541
- mean_return_pct: -0.08527
- total_pnl_dollars: -2647.73
- max_drawdown_dollars: -3147.45
- exit_reason_breakdown: {'time_exit': 64, 'stop_loss': 12}
- mean-return 95% bootstrap CI: (-0.15132, -0.02181)
- sharpe 95% bootstrap CI: (-4.074, -0.769)
- rejection reasons: mean-return 95% bootstrap CI (-0.15132, -0.02181) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.074, -0.769) does not exclude zero (lower bound must be > 0)

## cash_secured_put / DIA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4699
- profit_factor: 1.265
- sharpe: 0.957
- mean_return_pct: 0.00084
- total_pnl_dollars: 2861.23
- max_drawdown_dollars: -4476.25
- exit_reason_breakdown: {'expiration': 39, 'stop_loss': 44}
- mean-return 95% bootstrap CI: (-0.00082, 0.00249)
- sharpe 95% bootstrap CI: (-0.951, 2.938)
- rejection reasons: mean-return 95% bootstrap CI (-0.00082, 0.00249) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.951, 2.938) does not exclude zero (lower bound must be > 0)

## covered_call / DIA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3253
- profit_factor: 0.893
- sharpe: -0.414
- mean_return_pct: -0.00032
- total_pnl_dollars: -1020.01
- max_drawdown_dollars: -2104.93
- exit_reason_breakdown: {'stop_loss': 56, 'expiration': 27}
- mean-return 95% bootstrap CI: (-0.00187, 0.0011)
- sharpe 95% bootstrap CI: (-2.291, 1.623)
- rejection reasons: mean-return 95% bootstrap CI (-0.00187, 0.0011) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.291, 1.623) does not exclude zero (lower bound must be > 0)

## long_directional / DIA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.0843
- profit_factor: 0.357
- sharpe: -3.878
- mean_return_pct: -0.4344
- total_pnl_dollars: -15313.16
- max_drawdown_dollars: -16487.95
- exit_reason_breakdown: {'stop_loss': 73, 'expiration': 10}
- mean-return 95% bootstrap CI: (-0.63667, -0.20217)
- sharpe 95% bootstrap CI: (-11.243, -1.305)
- rejection reasons: mean-return 95% bootstrap CI (-0.63667, -0.20217) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-11.243, -1.305) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / DIA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4699
- profit_factor: 1.245
- sharpe: -0.24
- mean_return_pct: -0.00845
- total_pnl_dollars: 1580.14
- max_drawdown_dollars: -2115.31
- exit_reason_breakdown: {'expiration': 39, 'stop_loss': 44}
- mean-return 95% bootstrap CI: (-0.07748, 0.06066)
- sharpe 95% bootstrap CI: (-2.135, 1.889)
- rejection reasons: mean-return 95% bootstrap CI (-0.07748, 0.06066) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.135, 1.889) does not exclude zero (lower bound must be > 0)

## iron_condor / DIA -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3012
- profit_factor: 1.198
- sharpe: -0.645
- mean_return_pct: -0.01611
- total_pnl_dollars: 796.99
- max_drawdown_dollars: -1501.74
- exit_reason_breakdown: {'stop_loss': 58, 'expiration': 25}
- mean-return 95% bootstrap CI: (-0.06442, 0.02957)
- sharpe 95% bootstrap CI: (-2.56, 1.224)
- rejection reasons: mean-return 95% bootstrap CI (-0.06442, 0.02957) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.56, 1.224) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / DIA -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.6053
- profit_factor: 0.665
- sharpe: -1.77
- mean_return_pct: -0.05577
- total_pnl_dollars: -2198.03
- max_drawdown_dollars: -3387.81
- exit_reason_breakdown: {'time_exit': 68, 'stop_loss': 8}
- mean-return 95% bootstrap CI: (-0.11886, 0.00457)
- sharpe 95% bootstrap CI: (-3.425, 0.177)
- rejection reasons: mean-return 95% bootstrap CI (-0.11886, 0.00457) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-3.425, 0.177) does not exclude zero (lower bound must be > 0)


---

### Methodology note -- 2026-09-01T20:53:35+00:00

Bootstrap changed from i.i.d. resampling to a circular moving-block bootstrap, block length ceil(hold_days / step_days) per strategy. Measured on a zero-edge random walk, the i.i.d. gate passed 10.8% of samples against a 2.5% nominal rate; the block gate passes 2.5% (test_block_bootstrap.py).

**Every entry above this line was computed with the i.i.d. bootstrap and is superseded.** They are kept because a superseded result is still a record of what was tried, but no PASS above this line may be quoted as validated.

Block length this run: cash_secured_put=3, covered_call=3, long_directional=3, vertical_credit_spread=3, iron_condor=3, iron_condor_vrp_45_21=7, vertical_credit_spread_2d=1.

Note that vertical_credit_spread_2d has block length 1 legitimately: its entry step (7 days) exceeds its hold (2 days), so its trades share no price path and are genuinely independent. That is a property of the schedule, not an exemption.

---

## cash_secured_put / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4699
- profit_factor: 1.329
- sharpe: 1.33
- mean_return_pct: 0.00137
- total_pnl_dollars: 5204.51
- max_drawdown_dollars: -4025.89
- exit_reason_breakdown: {'stop_loss': 44, 'expiration': 39}
- mean-return 95% bootstrap CI: (-0.00098, 0.00393)
- sharpe 95% bootstrap CI: (-1.076, 3.504)
- rejection reasons: mean-return 95% bootstrap CI (-0.00098, 0.00393) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.076, 3.504) does not exclude zero (lower bound must be > 0)

## covered_call / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3976
- profit_factor: 1.565
- sharpe: 1.878
- mean_return_pct: 0.00525
- total_pnl_dollars: 23202.53
- max_drawdown_dollars: -10992.25
- exit_reason_breakdown: {'stop_loss': 49, 'expiration': 34}
- mean-return 95% bootstrap CI: (-0.00054, 0.01178)
- sharpe 95% bootstrap CI: (-0.235, 3.887)
- rejection reasons: mean-return 95% bootstrap CI (-0.00054, 0.01178) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.235, 3.887) does not exclude zero (lower bound must be > 0)

## long_directional / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.1566
- profit_factor: 0.528
- sharpe: -2.008
- mean_return_pct: -0.25576
- total_pnl_dollars: -14799.23
- max_drawdown_dollars: -18718.84
- exit_reason_breakdown: {'stop_loss': 68, 'expiration': 15}
- mean-return 95% bootstrap CI: (-0.53192, 0.05521)
- sharpe 95% bootstrap CI: (-7.177, 0.363)
- rejection reasons: mean-return 95% bootstrap CI (-0.53192, 0.05521) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-7.177, 0.363) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4458
- profit_factor: 1.052
- sharpe: -0.89
- mean_return_pct: -0.03284
- total_pnl_dollars: 541.99
- max_drawdown_dollars: -2847.21
- exit_reason_breakdown: {'stop_loss': 46, 'expiration': 37}
- mean-return 95% bootstrap CI: (-0.10719, 0.04486)
- sharpe 95% bootstrap CI: (-2.757, 1.354)
- rejection reasons: mean-return 95% bootstrap CI (-0.10719, 0.04486) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.757, 1.354) does not exclude zero (lower bound must be > 0)

## iron_condor / SPY -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4096
- profit_factor: 1.754
- sharpe: 1.099
- mean_return_pct: 0.03017
- total_pnl_dollars: 3961.4
- max_drawdown_dollars: -2320.88
- exit_reason_breakdown: {'stop_loss': 49, 'expiration': 34}
- mean-return 95% bootstrap CI: (-0.03392, 0.09307)
- sharpe 95% bootstrap CI: (-1.112, 3.99)
- rejection reasons: mean-return 95% bootstrap CI (-0.03392, 0.09307) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.112, 3.99) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / SPY -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5921
- profit_factor: 0.635
- sharpe: -2.191
- mean_return_pct: -0.07225
- total_pnl_dollars: -3640.3
- max_drawdown_dollars: -4794.01
- exit_reason_breakdown: {'time_exit': 66, 'stop_loss': 10}
- mean-return 95% bootstrap CI: (-0.18116, 0.02919)
- sharpe 95% bootstrap CI: (-4.831, 1.368)
- rejection reasons: mean-return 95% bootstrap CI (-0.18116, 0.02919) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.831, 1.368) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread_2d / SPY -- FAIL (2026-09-01)

- trades: 85
- win_rate: 0.7765
- profit_factor: 1.929
- sharpe: 1.665
- mean_return_pct: 0.07493
- total_pnl_dollars: 2941.79
- max_drawdown_dollars: -469.88
- exit_reason_breakdown: {'expiration': 73, 'stop_loss': 12}
- mean-return 95% bootstrap CI: (-0.01642, 0.15767)
- sharpe 95% bootstrap CI: (-0.323, 4.399)
- rejection reasons: mean-return 95% bootstrap CI (-0.01642, 0.15767) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.323, 4.399) does not exclude zero (lower bound must be > 0)

## cash_secured_put / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.5181
- profit_factor: 1.423
- sharpe: 1.596
- mean_return_pct: 0.00209
- total_pnl_dollars: 7387.05
- max_drawdown_dollars: -4225.21
- exit_reason_breakdown: {'stop_loss': 40, 'expiration': 43}
- mean-return 95% bootstrap CI: (-0.0007, 0.00521)
- sharpe 95% bootstrap CI: (-0.566, 3.935)
- rejection reasons: mean-return 95% bootstrap CI (-0.0007, 0.00521) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.566, 3.935) does not exclude zero (lower bound must be > 0)

## covered_call / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.4819
- profit_factor: 1.699
- sharpe: 2.293
- mean_return_pct: 0.00943
- total_pnl_dollars: 35542.24
- max_drawdown_dollars: -13241.52
- exit_reason_breakdown: {'stop_loss': 42, 'expiration': 41}
- mean-return 95% bootstrap CI: (-0.00028, 0.02025)
- sharpe 95% bootstrap CI: (-0.077, 4.433)
- rejection reasons: mean-return 95% bootstrap CI (-0.00028, 0.02025) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.077, 4.433) does not exclude zero (lower bound must be > 0)

## long_directional / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.2289
- profit_factor: 1.012
- sharpe: 0.456
- mean_return_pct: 0.09439
- total_pnl_dollars: 530.86
- max_drawdown_dollars: -12420.55
- exit_reason_breakdown: {'stop_loss': 55, 'expiration': 28}
- mean-return 95% bootstrap CI: (-0.35738, 0.64084)
- sharpe 95% bootstrap CI: (-2.487, 2.516)
- rejection reasons: mean-return 95% bootstrap CI (-0.35738, 0.64084) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.487, 2.516) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.494
- profit_factor: 1.112
- sharpe: 0.056
- mean_return_pct: 0.00205
- total_pnl_dollars: 1398.78
- max_drawdown_dollars: -3407.53
- exit_reason_breakdown: {'stop_loss': 42, 'expiration': 41}
- mean-return 95% bootstrap CI: (-0.07897, 0.08605)
- sharpe 95% bootstrap CI: (-2.119, 2.536)
- rejection reasons: mean-return 95% bootstrap CI (-0.07897, 0.08605) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.119, 2.536) does not exclude zero (lower bound must be > 0)

## iron_condor / QQQ -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3133
- profit_factor: 1.207
- sharpe: -0.056
- mean_return_pct: -0.00135
- total_pnl_dollars: 1400.48
- max_drawdown_dollars: -2504.55
- exit_reason_breakdown: {'stop_loss': 57, 'expiration': 26}
- mean-return 95% bootstrap CI: (-0.05469, 0.05387)
- sharpe 95% bootstrap CI: (-2.24, 2.467)
- rejection reasons: mean-return 95% bootstrap CI (-0.05469, 0.05387) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.24, 2.467) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / QQQ -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5921
- profit_factor: 0.521
- sharpe: -2.65
- mean_return_pct: -0.09088
- total_pnl_dollars: -6676.37
- max_drawdown_dollars: -8083.47
- exit_reason_breakdown: {'time_exit': 63, 'stop_loss': 13}
- mean-return 95% bootstrap CI: (-0.20134, 0.01382)
- sharpe 95% bootstrap CI: (-5.313, 0.546)
- rejection reasons: mean-return 95% bootstrap CI (-0.20134, 0.01382) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-5.313, 0.546) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread_2d / QQQ -- FAIL (2026-09-01)

- trades: 85
- win_rate: 0.8118
- profit_factor: 1.818
- sharpe: 1.812
- mean_return_pct: 0.08423
- total_pnl_dollars: 3449.94
- max_drawdown_dollars: -616.64
- exit_reason_breakdown: {'stop_loss': 9, 'expiration': 76}
- mean-return 95% bootstrap CI: (-0.00894, 0.17246)
- sharpe 95% bootstrap CI: (-0.166, 4.719)
- rejection reasons: mean-return 95% bootstrap CI (-0.00894, 0.17246) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.166, 4.719) does not exclude zero (lower bound must be > 0)

## cash_secured_put / IWM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.506
- profit_factor: 1.566
- sharpe: 1.901
- mean_return_pct: 0.00251
- total_pnl_dollars: 4226.74
- max_drawdown_dollars: -3338.42
- exit_reason_breakdown: {'expiration': 42, 'stop_loss': 41}
- mean-return 95% bootstrap CI: (-0.00059, 0.00583)
- sharpe 95% bootstrap CI: (-0.43, 4.703)
- rejection reasons: mean-return 95% bootstrap CI (-0.00059, 0.00583) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.43, 4.703) does not exclude zero (lower bound must be > 0)

## covered_call / IWM -- PASS (2026-09-01)

- trades: 83
- win_rate: 0.4699
- profit_factor: 1.882
- sharpe: 2.667
- mean_return_pct: 0.01009
- total_pnl_dollars: 17331.47
- max_drawdown_dollars: -6851.07
- exit_reason_breakdown: {'expiration': 39, 'stop_loss': 44}
- mean-return 95% bootstrap CI: (0.00138, 0.01954)
- sharpe 95% bootstrap CI: (0.426, 4.945)

## covered_call (extended history) / IWM -- PASS (2026-09-01)

- trades: 211
- win_rate: 0.4408
- profit_factor: 1.617
- sharpe: 3.337
- mean_return_pct: 0.00801
- total_pnl_dollars: 31034.0
- max_drawdown_dollars: -6851.07
- exit_reason_breakdown: {'stop_loss': 117, 'expiration': 94}
- mean-return 95% bootstrap CI: (0.00217, 0.01422)
- sharpe 95% bootstrap CI: (0.974, 5.649)

## covered_call (sub-period stability) / IWM -- FAIL (2026-09-01)

- trades: 105
- win_rate: 0.4
- profit_factor: 1.367
- sharpe: 1.706
- mean_return_pct: 0.0059
- total_pnl_dollars: 9616.96
- max_drawdown_dollars: -5380.94
- exit_reason_breakdown: {'stop_loss': 63, 'expiration': 42}
- mean-return 95% bootstrap CI: (-0.00242, 0.01452)
- sharpe 95% bootstrap CI: (-0.797, 3.927)
- rejection reasons: mean-return 95% bootstrap CI (-0.00242, 0.01452) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.797, 3.927) does not exclude zero (lower bound must be > 0)
- notes: second half: passed=True, sharpe=3.045

## long_directional / IWM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.0964
- profit_factor: 0.462
- sharpe: -2.062
- mean_return_pct: -0.29561
- total_pnl_dollars: -10262.03
- max_drawdown_dollars: -10262.03
- exit_reason_breakdown: {'stop_loss': 72, 'expiration': 11}
- mean-return 95% bootstrap CI: (-0.54301, -0.00143)
- sharpe 95% bootstrap CI: (-7.074, -0.008)
- rejection reasons: mean-return 95% bootstrap CI (-0.54301, -0.00143) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-7.074, -0.008) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread / IWM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.494
- profit_factor: 1.349
- sharpe: 0.615
- mean_return_pct: 0.0208
- total_pnl_dollars: 1744.85
- max_drawdown_dollars: -1787.2
- exit_reason_breakdown: {'expiration': 41, 'stop_loss': 42}
- mean-return 95% bootstrap CI: (-0.05935, 0.09853)
- sharpe 95% bootstrap CI: (-1.706, 3.24)
- rejection reasons: mean-return 95% bootstrap CI (-0.05935, 0.09853) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-1.706, 3.24) does not exclude zero (lower bound must be > 0)

## iron_condor / IWM -- FAIL (2026-09-01)

- trades: 83
- win_rate: 0.3735
- profit_factor: 1.419
- sharpe: 0.236
- mean_return_pct: 0.00619
- total_pnl_dollars: 1320.24
- max_drawdown_dollars: -1222.76
- exit_reason_breakdown: {'stop_loss': 52, 'expiration': 31}
- mean-return 95% bootstrap CI: (-0.05773, 0.0691)
- sharpe 95% bootstrap CI: (-2.076, 2.932)
- rejection reasons: mean-return 95% bootstrap CI (-0.05773, 0.0691) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-2.076, 2.932) does not exclude zero (lower bound must be > 0)

## iron_condor_vrp_45_21 / IWM -- FAIL (2026-09-01)

- trades: 76
- win_rate: 0.5921
- profit_factor: 0.551
- sharpe: -2.541
- mean_return_pct: -0.08527
- total_pnl_dollars: -2647.73
- max_drawdown_dollars: -3147.45
- exit_reason_breakdown: {'time_exit': 64, 'stop_loss': 12}
- mean-return 95% bootstrap CI: (-0.19122, 0.01149)
- sharpe 95% bootstrap CI: (-4.911, 0.485)
- rejection reasons: mean-return 95% bootstrap CI (-0.19122, 0.01149) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-4.911, 0.485) does not exclude zero (lower bound must be > 0)

## vertical_credit_spread_2d / IWM -- FAIL (2026-09-01)

- trades: 85
- win_rate: 0.7647
- profit_factor: 1.796
- sharpe: 1.665
- mean_return_pct: 0.07326
- total_pnl_dollars: 1415.28
- max_drawdown_dollars: -237.07
- exit_reason_breakdown: {'expiration': 74, 'stop_loss': 11}
- mean-return 95% bootstrap CI: (-0.01312, 0.15925)
- sharpe 95% bootstrap CI: (-0.263, 4.566)
- rejection reasons: mean-return 95% bootstrap CI (-0.01312, 0.15925) does not exclude zero (lower bound must be > 0); Sharpe 95% bootstrap CI (-0.263, 4.566) does not exclude zero (lower bound must be > 0)

