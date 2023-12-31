import numpy as np
import pandas as pd
import pickle
from yaml import safe_load
from tqdm import tqdm
from logger import logging
import os

filenames = []
for file in os.listdir('data'):
    filenames.append(os.path.join('data',file))
    
final_df = pd.DataFrame()
counter = 1
for file in tqdm(filenames):
    with open(file, 'r') as f:
        df = pd.json_normalize(safe_load(f))
        df['match_id'] = counter
        final_df =pd.concat([final_df,df])
        counter+=1

logging.info("yaml files loaded successfully")
 
 
logging.info("data transformation has been initiated")

final_df.drop(columns=[
    'meta.data_version',
    'meta.created',
    'meta.revision',
    'info.outcome.bowl_out',
    'info.bowl_out',
    'info.supersubs.South Africa',
    'info.supersubs.New Zealand',
    'info.outcome.eliminator',
    'info.outcome.result',
    'info.outcome.method',
    'info.neutral_venue',
    'info.match_type_number',
    'info.outcome.by.runs',
    'info.outcome.by.wickets'
],inplace=True)

final_df = final_df[final_df['info.gender'] == 'male']
final_df.drop(columns=['info.gender'],inplace=True)

final_df = final_df[final_df['info.overs'] == 20]
final_df.drop(columns=['info.overs','info.match_type'],inplace=True)

matches=pd.DataFrame()
matches = pd.concat([matches ,final_df])

count = 1
delivery_df = pd.DataFrame()
for index, row in matches.iterrows():
    if count in [75,108,150,180,268,360,443,458,584,748,982,1052,1111,1226,1345]:
        count+=1
        continue
    count+=1
    ball_of_match = []
    batsman = []
    bowler = []
    runs = []
    player_of_dismissed = []
    teams = []
    batting_team = []
    match_id = []
    city = []
    venue = []
    for ball in row['innings'][0]['1st innings']['deliveries']:
        for key in ball.keys():
            match_id.append(count)
            batting_team.append(row['innings'][0]['1st innings']['team'])
            teams.append(row['info.teams'])
            ball_of_match.append(key)
            batsman.append(ball[key]['batsman'])
            bowler.append(ball[key]['bowler'])
            runs.append(ball[key]['runs']['total'])
            city.append(row['info.city'])
            venue.append(row['info.venue'])
            try:
                player_of_dismissed.append(ball[key]['wicket']['player_out'])
            except:
                player_of_dismissed.append('0')
    loop_df = pd.DataFrame({
            'match_id':match_id,
            'teams':teams,
            'batting_team':batting_team,
            'ball':ball_of_match,
            'batsman':batsman,
            'bowler':bowler,
            'runs':runs,
            'player_dismissed':player_of_dismissed,
            'city':city,
            'venue':venue
        })
    delivery_df = pd.concat([delivery_df,loop_df])

def bowl(row):
    for team in row['teams']:
        if team != row['batting_team']:
            return team
        
delivery_df['bowling_team'] = delivery_df.apply(bowl,axis=1)
delivery_df.drop(columns=['teams'],inplace=True)

teams = [
    'Australia',
    'India',
    'Bangladesh',
    'New Zealand',
    'South Africa',
    'England',
    'West Indies',
    'Afghanistan',
    'Pakistan',
    'Sri Lanka'    
]

delivery_df = delivery_df[delivery_df['batting_team'].isin(teams)]
delivery_df = delivery_df[delivery_df['bowling_team'].isin(teams)]

df = delivery_df[['match_id','batting_team','bowling_team','ball','runs','player_dismissed','city','venue']]

cities = np.where(df['city'].isnull(),df['venue'].str.split().apply(lambda x:x[0]),df['city'])
df['city'] = cities
df.drop(columns=['venue'],inplace=True)

eligible_cities = df['city'].value_counts()[df['city'].value_counts() > 600].index.tolist()

df = df[df['city'].isin(eligible_cities)]

#df['current_score']=df['current_score'].astype('int')
df['match_id']=df['match_id'].astype('int')
df['runs']=df['runs'].astype('int')
current_score=[]
current_score = df.groupby('match_id')['runs'].cumsum()
df['current_score']=current_score
df['over'] = df['ball'].apply(lambda x:str(x).split(".")[0])
df['ball_no'] = df['ball'].apply(lambda x:str(x).split(".")[1])

df['balls_bowled'] = (df['over'].astype('int')*6) + df['ball_no'].astype('int')

df['balls_left'] = 120 - df['balls_bowled']
df['balls_left'] = df['balls_left'].apply(lambda x:0 if x<0 else x)

df['player_dismissed'] = df['player_dismissed'].apply(lambda x:0 if x=='0' else 1)
df['player_dismissed'] = df['player_dismissed'].astype('int')
df['player_dismissed'] = df.groupby('match_id')['player_dismissed'].cumsum()
df['wickets_left'] = 10 - df['player_dismissed']

df['crr'] = (df['current_score']*6)/df['balls_bowled']

groups = df.groupby('match_id')

match_ids = df['match_id'].unique()
last_five = []
for id in match_ids:
    group_data = groups.get_group(id)
    rolling_sum = group_data['runs'].rolling(window=30).sum()
    last_five.extend(rolling_sum.values.tolist())


df['last_five'] = last_five

final_df = df.groupby('match_id').sum()['runs'].reset_index().merge(df,on='match_id')

final_df=final_df[['batting_team','bowling_team','city','current_score','balls_left','wickets_left','crr','last_five','runs_x']]

final_df.dropna(inplace=True)

pickle.dump(final_df,open('data_transformation.pkl','wb'))

logging.info("data transformation has been completed")
os.system('python model_trainer.py')
