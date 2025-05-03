import pandas as pd
import numpy as np
import json
from dataclasses import dataclass
from itertools import product

def allocate(order_size, venues, lambda_over, lambda_under, theta_queue):
    step = 100
    splits = [[]]
    for v in range(len(venues)):
        new_splits = []
        for alloc in splits:
            used = sum(alloc)
            max_v = min(order_size - used, venues[v].ask_size)
            for q in range(0, max_v+1, step):
                new_splits.append(alloc + [q])
        splits = new_splits
    best_cost = float('inf')
    best_split = []
    for alloc in splits:
        if sum(alloc) != order_size:
            continue
        cost = compute_cost(alloc, venues, order_size, lambda_over, lambda_under, theta_queue)
        if cost < best_cost:
            best_cost = cost
            best_split = alloc
    return best_split, best_cost


def compute_cost(split, venues, order_size, lambda_over, lambda_under, theta_queue):
    executed = 0
    cash_spent = 0
    for i in range(0, len(venues) - 1):
        exe = min(split[i], venues[i].ask_size)
        executed += exe
        cash_spent += exe * (venues[i].ask + venues[i].fee)
        maker_rebate = max(split[i] - exe, 0) * venues[i].rebate
        cash_spent -= maker_rebate
    underfill = max(order_size - executed, 0)
    overfill = max(executed - order_size, 0)
    risk_pen = theta_queue * (underfill + overfill)
    cost_pen = lambda_under * underfill + lambda_over * overfill
    return cash_spent + risk_pen + cost_pen


def Best_Ask_Strategy(df,order_size=5000):
    remaining_size = order_size
    cash_spent = 0
    total_executed_size = 0
    df_first = df.drop_duplicates(subset='ts_event', keep='first').copy()
    df_sorted = df_first.sort_values(by='ask_px_00', ascending=True).reset_index(drop=True)
    for _, row in df_sorted.iterrows():
        size = row['ask_sz_00']
        executed_size = min(remaining_size, size)
        remaining_size -= executed_size
        total_executed_size += executed_size
        cash_spent += executed_size*row['ask_px_00']

    avg_price = cash_spent/total_executed_size if total_executed_size > 0 else None
    return {'total_cash_spent': cash_spent, 'avg_fill_price': avg_price}


def TWAP_Strategy(df,order_size=5000):
    df_first = df.drop_duplicates(subset='ts_event', keep='first').copy()
    remaining_size = order_size
    cash_spent = 0
    total_executed_size = 0
    df_first['ts_event'] = pd.to_datetime(df_first['ts_event'])
    df_first['bucket'] = df_first['ts_event'].dt.floor('60s')
    bucket_size = order_size / df_first['bucket'].nunique()

    for _, group in df_first.groupby('bucket', sort=False):
        if remaining_size <= 0:
            break
        idx = group["ask_px_00"].idxmin()
        price = group.loc[idx]['ask_px_00']
        size = group.loc[idx]['ask_sz_00']
        executed_size = min(remaining_size, size, bucket_size)
        remaining_size -= executed_size
        total_executed_size += executed_size
        cash_spent += executed_size * price

    avg_price = cash_spent/total_executed_size if total_executed_size > 0 else None
    return {'total_cash_spent': cash_spent, 'avg_fill_price': avg_price}

def VWAP_Strategy(df,order_size=5000):
    df_first = df.drop_duplicates(subset='ts_event', keep='first').copy()
    venue_stats = (
        df_first
        .groupby('publisher_id')
        .apply(lambda g: pd.Series({
            'total_ask_size': g['ask_sz_00'].sum(),
            'avg_ask_px': (g['ask_px_00'] * g['ask_sz_00']).sum() / g['ask_sz_00'].sum()
        }))
        .reset_index()
    )

    total_ask_size = venue_stats['total_ask_size'].sum()
    venue_stats['alloc'] = venue_stats['total_ask_size'] / total_ask_size  * order_size
    remaining_size = order_size
    cash_spent = 0
    total_executed_size = 0
    for _, row in venue_stats.iterrows():
        if remaining_size <= 0:
            break
        executed_size = min(remaining_size, row['total_ask_size'],row["alloc"])
        cash_spent += executed_size * row['avg_ask_px']
        remaining_size -= executed_size
        total_executed_size += executed_size

    avg_price = cash_spent / total_executed_size if total_executed_size > 0 else None
    return {'total_cash_spent': cash_spent, 'avg_fill_price': avg_price}

def Smart_Order_Router_Params(df, order_size, lambda_over,lambda_under,theta_queue):
    @dataclass
    class Venue:
        ask: float
        ask_size: int
        fee: float = 0.0
        rebate: float = 0.0

    remaining_size = order_size
    cash_spent = 0
    total_executed_size = 0
    df_first = df.drop_duplicates(subset='ts_event', keep='first').copy()
    venues = []
    for _, venue_df in df_first.groupby('publisher_id', sort=False):
        idx = venue_df["ask_px_00"].idxmin()
        price = venue_df.iloc[idx]['ask_px_00']
        size = venue_df['ask_sz_00'].sum()
        venue = Venue(price,size,0.0025,0.0005)
        venues.append(venue)
    best_split, best_cost = allocate(remaining_size, venues, lambda_over, lambda_under, theta_queue)
    for i , alloc in enumerate(best_split):
        executed_size = min(remaining_size, venues[i].ask_size, alloc)
        cash_spent += executed_size * venues[i].ask
        remaining_size -= executed_size
        total_executed_size += executed_size
    avg_price = cash_spent / total_executed_size if total_executed_size > 0 else None
    params = {'lambda_over': lambda_over, 'lambda_under': lambda_under, 'theta_queue': theta_queue}
    return {'params': params, 'best_cost':best_cost, 'total_cash_spent': cash_spent, 'avg_fill_price': avg_price}

def Smart_Order_Router_Strategy(df, order_size, lambda_over_list, lambda_under_list, theta_queue_list):
    overall_best_cost = None
    best_params = None
    cash_spent = None
    avg_price = None
    for lambda_over, lambda_under, theta_queue in product(lambda_over_list, lambda_under_list, theta_queue_list):
        result = Smart_Order_Router_Params(df, order_size, lambda_over, lambda_under, theta_queue)
        best_cost = result['best_cost']
        if overall_best_cost is None or overall_best_cost < best_cost:
            overall_best_cost = best_cost
            best_params = result['params']
            cash_spent = result['total_cash_spent']
            avg_price = result['avg_fill_price']
    return {'best_params': best_params, 'best_cost':overall_best_cost, 'total_cash_spent': cash_spent, 'avg_fill_price': avg_price}

def main():
    order_size = 5000
    df = pd.read_csv('l1_day.csv', usecols =['ts_event','publisher_id','ask_px_00','ask_sz_00'])
    lambda_over_list = [0.01, 0.05, 0.1,0.025]
    lambda_under_list = [0.01, 0.05, 0.1,0.025]
    theta_queue_list = [0.001, 0.005, 0.01,0.025]
    best_ask_strategy_result = Best_Ask_Strategy(df, order_size)
    TWAP_strategy_result = TWAP_Strategy(df, order_size)
    VWAP_strategy_result = VWAP_Strategy(df, order_size)
    smart_order_router_strategy_result = Smart_Order_Router_Strategy(df, order_size, lambda_over_list, lambda_under_list, theta_queue_list)
    result = {
        'best_parameters': smart_order_router_strategy_result['best_params'],
        'smart_order_router': {'total_cash_spent': smart_order_router_strategy_result['total_cash_spent'],
                               'avg_fill_price': smart_order_router_strategy_result['avg_fill_price']},
        'best_ask': best_ask_strategy_result,
        'twap': TWAP_strategy_result,
        'vwap': VWAP_strategy_result,
        'savings_bps': {}
    }
    for name, base in [('best_ask', best_ask_strategy_result), ('twap', TWAP_strategy_result), ('vwap', VWAP_strategy_result)]:
        if base['avg_fill_price'] and smart_order_router_strategy_result['avg_fill_price']:
            result['savings_bps'][name] = (base['avg_fill_price'] - smart_order_router_strategy_result['avg_fill_price']) / base[
                'avg_fill_price'] * 10000
        else:
            result['savings_bps'][name] = None

    json_result = json.dumps(result, indent=4)
    print(json_result)

if __name__ == '__main__':
    main()


