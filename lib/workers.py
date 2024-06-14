import os
import pandas as pd
import sys
from pathlib import Path
import yaml
import matsim
import sqlalchemy
from tqdm import tqdm
import geopandas as gpd
from shapely.geometry import mapping
import random
from geopandas import GeoDataFrame
from shapely.geometry import Point


ROOT_dir = Path(__file__).parent.parent
sys.path.append(ROOT_dir)
sys.path.insert(0, os.path.join(ROOT_dir, '/lib'))
#with open(os.path.join(ROOT_dir, 'dbs', 'keys.yaml')) as f:
#    keys_manager = yaml.load(f, Loader=yaml.FullLoader)


def shp2poly(filename=None, targetfile=None):
    """
    Convert a given shapefile to a .poly file for the use by osmosis.
    :param filename: str, file path of the shape file
    :param targetfile: str, target .poly file
    """
    gdf_city_boundary = gpd.GeoDataFrame.from_file(filename).to_crs(4326)
    g = [i for i in gdf_city_boundary.geometry]
    all_coords = mapping(g[0])["coordinates"][0]
    F = open(targetfile, "w")
    F.write("polygon\n")
    F.write("1\n")
    for point in all_coords:
        F.write("\t" + str(point[0]) + "\t" + str(point[1]) + "\n")
    F.write("END\n")
    F.write("END\n")
    F.close()


def personplan2df(person, plan, output=True, experienced=False):
    """
    Convert a person's activity plan from MATSim format to a dataframe.
    :param person: matsim.plan_reader() object
    :param plan: matsim.plan_reader() object
    :param output: whether read in output file
    :param experienced: whether read in experienced plans
    :return: a re-organised individual activity plan executed by matsim (dataframe)
    """
    pid = person.attrib['id']

    activities = filter(lambda x: x.tag == 'activity', plan)
    types = [activity.attrib['type'] for activity in activities]
    activities = filter(lambda x: x.tag == 'activity', plan)
    end_times = []
    for activity in activities:
        try:
            end_times.append(activity.attrib['end_time'])
        except:
            end_times.append('23:59:59')
    if experienced:
        activities = filter(lambda x: x.tag == 'activity', plan)
        xs = [0]
        count = 0
        for activity in activities:
            if count != 0:
                xs.append(activity.attrib['x'])
            count += 1
        activities = filter(lambda x: x.tag == 'activity', plan)
        ys = [0]
        count = 0
        for activity in activities:
            if count != 0:
                ys.append(activity.attrib['y'])
            count += 1
    else:
        activities = filter(lambda x: x.tag == 'activity', plan)
        xs = [activity.attrib['x'] for activity in activities]
        activities = filter(lambda x: x.tag == 'activity', plan)
        ys = [activity.attrib['y'] for activity in activities]

    legs = filter(lambda x: x.tag == 'leg', plan)
    modes = [leg.attrib['mode'] for leg in legs]
    modes = [''] + modes

    df = pd.DataFrame()
    df.loc[:, 'act_purpose'] = types
    df.loc[:, 'PId'] = pid
    df.loc[:, 'act_end'] = end_times
    df.loc[:, 'act_id'] = range(0, len(types))
    df.loc[:, 'mode'] = modes
    df.loc[:, 'POINT_X'] = xs
    df.loc[:, 'POINT_Y'] = ys

    if output:
        legs = filter(lambda x: x.tag == 'leg', plan)
        trav_times = [leg.attrib['trav_time'] for leg in legs]
        trav_times = ["00:00:00"] + trav_times

        legs = filter(lambda x: x.tag == 'leg', plan)
        dep_times = [leg.attrib['dep_time'] for leg in legs]
        dep_times = ["00:00:00"] + dep_times

        legs = filter(lambda x: x.tag == 'leg', plan)
        distances = [0]
        for leg in legs:
            routes = filter(lambda x: x.tag == 'route', leg)
            distances += [float(route.attrib['distance']) / 1000 for route in routes]

        df.loc[:, 'dep_time'] = dep_times
        df.loc[:, 'trav_time'] = trav_times
        df.loc[:, 'distance'] = distances
        df.loc[:, 'score'] = float(plan.attrib['score'])
    else:
        df.loc[:, 'dep_time'] = ["00:00:00"] + list(df.loc[:, 'act_end'].values[:-1])
        # df.loc[:, 'trav_time'] = 0  # Only for output
        # df.loc[:, 'distance'] = 0  # Only for output
        # df.loc[:, 'speed'] = 0  # Only for output
        df.loc[:, 'src'] = 'input'
        df.loc[:, 'score'] = 0
    return df


def plans_summary(df):
    """
    :param df: dataframe, containing multiple agents' plans
    :return: dataframe, containing multiple agents' plans with more information
    """
    # calculate travel time
    df.loc[:, 'trav_time_min'] = df.trav_time.apply(lambda x: pd.Timedelta("0 days " + x))
    df.loc[:, 'trav_time_min'] = df.loc[:, 'trav_time_min'].apply(lambda x: x.seconds / 60)
    df.loc[:, 'speed'] = df.loc[:, 'distance'] / (df.loc[:, 'trav_time_min'] / 60)  # km/h

    # act_end - dep_time + trav_time = act_time for 1:
    df.loc[:, 'act_end_t'] = df.act_end.apply(
        lambda x: pd.Timedelta("0 days " + x) if x.split(':')[0] != '24' else pd.Timedelta(
            "1 days " + ':'.join(['00'] + x.split(':')[1:])))
    df.loc[:, 'dep_time_t'] = df.dep_time.apply(
        lambda x: pd.Timedelta("0 days " + x) if x.split(':')[0] != '24' else pd.Timedelta(
            "1 days " + ':'.join(['00'] + x.split(':')[1:])))
    df.loc[:, 'trav_time_t'] = df.trav_time.apply(lambda x: pd.Timedelta("0 days " + x))
    df.loc[:, 'act_time'] = df.apply(
        lambda row: (row['act_end_t'].seconds - row['dep_time_t'].seconds - row['trav_time_t'].seconds) / 60 if row[
                                                                                                                    'act_id'] != 0 else
        row['act_end_t'].seconds / 60, axis=1)
    # df.loc[:, 'act_time'] = df.loc[:, 'act_time'].apply(lambda x: x if x <= 1440 else x - 1440)
    df.drop(columns=['act_end_t', 'dep_time_t', 'trav_time_t'], inplace=True)

    # Convert act_end into the input format
    df.loc[:, 'act_end'] = df.act_end.apply(
        lambda x: pd.Timedelta("0 days " + x) if x.split(':')[0] != '24' else pd.Timedelta(
            "1 days " + ':'.join(['00'] + x.split(':')[1:])))
    df.loc[:, 'act_end'] = df.act_end.apply(lambda x: x.seconds / 3600)

    # Convert act_end into the input format
    df.loc[:, 'dep_time'] = df.dep_time.apply(
        lambda x: pd.Timedelta("0 days " + x) if x.split(':')[0] != '24' else pd.Timedelta(
            "1 days " + ':'.join(['00'] + x.split(':')[1:])))
    df.loc[:, 'dep_time'] = df.dep_time.apply(lambda x: x.seconds / 3600)  # hour
    df.loc[:, 'src'] = 'output'
    return df


def matsim_events2parquet(region=None, batch=None, test=False):
    """
    Write MATSim output events to the database.
    :param region: str, scenario name
    :param test: boolean, whether to do a test
    """
    file_path2output = os.path.join(ROOT_dir, f'dbs/scenarios/{region}/output_{batch}/output_events.xml.gz')
    selected_types = ['actend', 'actstart', 'vehicle enters traffic',
                      'left link', 'vehicle leaves traffic', 'PersonEntersVehicle', 'PersonLeavesVehicle']
    selected_vars = ['person', 'vehicle', 'time', 'type', 'actType', 'link']
    events = matsim.event_reader(file_path2output, types=','.join(selected_types))
    events_list = []
    for event in tqdm(events, desc='Streaming events'):
        to_delete = set(event.keys()).difference(selected_vars)
        for d in to_delete:
            del event[d]
        events_list.append(event)
    df2write = pd.DataFrame.from_records(events_list)
    # df2write = df2write[~df2write['person'].str.contains('_')]
    target_file = os.path.join(ROOT_dir, f'dbs/output/events_{batch}.parquet')
    df2write.to_parquet(target_file, index=False)


def eventsdb2batches(region=None, batch_num=20, network=None, geo=None):
    """
    Divide the database-stored events into batches for further analysis.
    :param geo: geodataframe, geometry, original link_id
    :param network: geodataframe, geometry, new link_id of combined network
    :param region: str, region name
    :param batch_num: int, number of batches
    """
    user = keys_manager['database']['user']
    password = keys_manager['database']['password']
    port = keys_manager['database']['port']
    db_name = keys_manager['database']['name']
    engine = sqlalchemy.create_engine(f'postgresql://{user}:{password}@localhost:{port}/{db_name}?gssencmode=disable')
    # Connect to PostgreSQL server
    dbConnection = engine.connect()
    # Read data from PostgreSQL database table and load into a DataFrame instance
    df_event = pd.read_sql(f'''select * from {region} order by person, time, type DESC;''', dbConnection)

    # Process link id to make it consistent with the combined network
    gdf_event = pd.merge(df_event, geo.loc[:, ['link_id', 'geometry']],
                         left_on='link', right_on='link_id', how='left')
    gdf_event = pd.merge(gdf_event.drop(columns=['link_id']), network[['link_id', 'geometry']],
                         on='geometry', how='left')
    df_event = gdf_event.drop(columns=['geometry'])
    del gdf_event

    print('Creating batches of events...')
    agents_car = df_event.loc[:, 'person'].unique()
    num_agents = len(agents_car)
    batch_num = batch_num
    batch_size = num_agents // batch_num
    if num_agents % batch_num == 0:
        batch_seq = list(range(0, batch_num)) * batch_size
    else:
        batch_seq = list(range(0, batch_num)) * batch_size + list(range(0, num_agents % batch_num))
    random.Random(4).shuffle(batch_seq)
    agents_car_batch_dict = {person: bt for person, bt in zip(agents_car, batch_seq)}
    df_event.loc[:, 'batch'] = df_event.loc[:, 'person'].map(agents_car_batch_dict)
    print(f'Number of car agents: {num_agents}.')

    batch_id = 0
    for _, data in tqdm(df_event.groupby('batch'), desc='Saving batches'):
        data.to_csv(os.path.join(ROOT_dir, f'dbs/events/{region}_events_batch{batch_id}.csv.gz'),
                    index=False, compression="gzip")
        batch_id += 1


def df2gdf_point(df, x_field, y_field, crs=4326, drop=True):
    """
    Convert two columns of GPS coordinates into POINT geo dataframe
    :param drop: boolean, if true, x and y columns will be dropped
    :param df: dataframe, containing X and Y
    :param x_field: string, col name of X
    :param y_field: string, col name of Y
    :param crs: int, epsg code
    :return: a geo dataframe with geometry of POINT
    """
    geometry = [Point(xy) for xy in zip(df[x_field], df[y_field])]
    if drop:
        gdf = GeoDataFrame(df.drop(columns=[x_field, y_field]), geometry=geometry)
    else:
        gdf = GeoDataFrame(df, crs=crs, geometry=geometry)
    gdf.set_crs(epsg=crs, inplace=True)
    return gdf