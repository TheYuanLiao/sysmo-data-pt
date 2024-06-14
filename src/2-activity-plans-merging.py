import sys
from pathlib import Path
import os
import pandas as pd
from tqdm import tqdm
import matsim
import datetime


ROOT_dir = Path(__file__).parent.parent
sys.path.append(ROOT_dir)
sys.path.insert(0, os.path.join(ROOT_dir, 'lib'))

import workers as workers


def trav_time_cal(data):
    data.loc[:, 'trav_time_min'] = [0.0] + [y-x for x, y in zip(data['act_end'].values[:-1], data['act_start'].values[1:])]
    return data


# Delta time format conversion
def digi2string(delta_time):
    hours = int(delta_time)
    minutes = int((delta_time - hours) * 60)
    seconds = int((delta_time - hours - minutes / 60) * 3600)
    time_delta = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
    # Format the time as "hh:mm:ss"
    formatted_time = str(time_delta)

    # If you want to remove the days part (if present)
    if 'days' in formatted_time:
        formatted_time = formatted_time.split(', ')[-1]
    return formatted_time


class PlansProcessor:
    def __int__(self):
        self.df_plan = None
        self.input = None
        self.output = None

    def load_original_plans(self):
        print("Loading original activity plans...")
        self.df_plan = pd.read_pickle(os.path.join(ROOT_dir, 'dbs/sysmo/df_act_plan.pkl'))
        self.df_plan = self.df_plan.loc[:, ['PId', 'act_id', 'act_start', 'act_end']]. \
            sort_values(by=['PId', 'act_id'], ascending=True)
        self.df_plan.PId = self.df_plan.PId.astype(str)

    def load_input_plans(self, batch=None, test=False):
        input_file = os.path.join(ROOT_dir, f'dbs/scenarios/sweden/plans_{batch}.xml.gz')
        plans = matsim.plan_reader(input_file)
        list_df_tst = []
        if test:
            tst = 0
            for person, plan in plans:
                list_df_tst.append(workers.personplan2df(person, plan, output=False, experienced=False))
                tst += 1
                if tst == 99:
                    break
        else:
            for person, plan in tqdm(plans, desc='Reading plans'):
                list_df_tst.append(workers.personplan2df(person, plan, output=False, experienced=False))
        self.input = pd.concat(list_df_tst)

        # Process travel time
        df_plan_trav = self.df_plan.loc[self.df_plan.PId.isin(self.input.PId.unique()), :]
        tqdm.pandas()
        df_plan_trav = df_plan_trav.groupby('PId').progress_apply(trav_time_cal).reset_index(drop=True)

        tqdm.pandas()
        df_plan_trav.loc[:, 'trav_time'] = df_plan_trav.loc[:, 'trav_time_min'].progress_apply(lambda x: digi2string(x))
        df_plan_trav.loc[:, 'trav_time_min'] *= 60
        df_plan_trav.loc[:, 'act_time'] = df_plan_trav.apply(
            lambda row: 60 * (row['act_end'] - row['act_start']) if row['act_end'] > row['act_start'] else 60 * (
                    row['act_end'] + 24 - row['act_start']), axis=1)

        self.input = pd.merge(self.input,
                              df_plan_trav[['PId', 'act_id', 'trav_time', 'trav_time_min', 'act_time']],
                              on=['PId', 'act_id'], how='left')

    def load_output_plans(self, batch=None):
        output_file = os.path.join(ROOT_dir, f'dbs/scenarios/sweden/output_{batch}/output_experienced_plans.xml.gz')
        plans = matsim.plan_reader(output_file)
        # Aggregate all individuals' plans
        self.output = workers.plans_summary(
            pd.concat([workers.personplan2df(person, plan, output=True, experienced=True)
                       for person, plan in
                       tqdm(plans, desc='Processing individual plan')]))
        self.output.PId = self.output.PId.astype(str)
        self.output.loc[:, 'act_end'] = self.output.loc[:, 'act_end'].progress_apply(lambda x: digi2string(x))
        self.output.loc[:, 'dep_time'] = self.output.loc[:, 'dep_time'].progress_apply(lambda x: digi2string(x))

    def add_distance_speed2input(self):
        self.input = pd.merge(self.input, self.output[['PId', 'act_id', 'distance']], on=['PId', 'act_id'])
        self.input.loc[:, 'speed'] = self.input.loc[:, 'distance'] / (self.input.loc[:, 'trav_time_min'] / 60)  # in km/h


if __name__ == '__main__':
    ps = PlansProcessor()
    ps.load_original_plans()
    for batch in range(0, 10):
        print(f'Processing batch {batch}')
        ps.load_input_plans(batch=batch, test=False)
        ps.load_output_plans(batch=batch)
        ps.add_distance_speed2input()
        df = pd.concat([ps.input, ps.output])
        df.to_csv(os.path.join(ROOT_dir, f'dbs/output/plans_{batch}.csv.gz'), compression='gzip', index=False)
