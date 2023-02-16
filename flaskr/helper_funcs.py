import sqlite3
import datetime
import requests
import pymysql
from flask import (
   g, current_app, session
)

def init_app(app):
    app.teardown_appcontext(close_db)

def create_scores_table(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS scores (id VARCHAR(100), Home_Team VARCHAR(100), Home_Team_Score FLOAT(7,2), Away_Team VARCHAR(100), Away_Team_Score  FLOAT(7,2),  PRIMARY KEY (id))')

def create_ML_table(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS moneyline (id VARCHAR(100), sport_key VARCHAR(50), Home_Team VARCHAR(100), Home_Team_Dec_Odds FLOAT(7,2), Away_Team VARCHAR(100), Away_Team_Dec_Odds FLOAT(7,2), book  VARCHAR(50), Start_Time DATETIME, Insert_Time DATETIME, CONSTRAINT id_book_time PRIMARY KEY (id,book, Insert_Time))')
    
def create_spreads_table(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS spreads (id VARCHAR(100), sport_key VARCHAR(50), Home_Team VARCHAR(100), Home_Team_Spread FLOAT(7,2), Home_Team_Odds FLOAT(7,2), Away_Team VARCHAR(100), Away_Team_Spread FLOAT(7,2), Away_Team_Odds FLOAT(7,2), book  VARCHAR(50), Start_Time DATETIME, Insert_Time DATETIME, CONSTRAINT id_book_time PRIMARY KEY (id,book, Insert_Time))')

def create_balance_table(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS balance (username VARCHAR(100),book VARCHAR(50), amount FLOAT(7,2), CONSTRAINT user_and_book PRIMARY KEY (username,book))')

def createSpreadBetsTable(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS spread_bets (id VARCHAR(100), sportkey VARCHAR(100),team_bet_on VARCHAR(100), book_bet_at VARCHAR(100), amount_bet FLOAT(7,2), spread_offered FLOAT(7,2), line_offered FLOAT(7,2), username VARCHAR(100), settled INT, CONSTRAINT id_book_team_user PRIMARY KEY (id,team_bet_on,book_bet_at, username))')

def createMLBetsTable(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS ml_bets (id VARCHAR(100), sportkey VARCHAR(100),team_bet_on VARCHAR(100), book_bet_at VARCHAR(100), amount_bet FLOAT(7,2), line_offered FLOAT(7,2), username VARCHAR(100), settled INT, CONSTRAINT id_book_team_user PRIMARY KEY (id,team_bet_on,book_bet_at,username))')

def create_users_table(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER AUTO_INCREMENT, username VARCHAR(100), password VARCHAR(100), PRIMARY KEY (id))')

def get_db():
    g.connection = pymysql.connect(host = current_app.config['DBENDPOINT'], user = current_app.config['USERNAME'], password = current_app.config['PW'], database = current_app.config['DB'], autocommit=True)
    g.cursor = g.connection.cursor()
    create_scores_table(g.cursor)
    create_ML_table(g.cursor)
    create_spreads_table(g.cursor)
    create_balance_table(g.cursor)
    createSpreadBetsTable(g.cursor)
    createMLBetsTable(g.cursor)
    create_users_table(g.cursor)

def close_db(e=None):
    db = g.pop('connection', None)

    if db is not None:
        db.close()

def get_inseason_sports():
    #will query api for the in season sports and returns the keys of these sports
    api = current_app.config['API']
    apikey = current_app.config['APIKEY']
    query_params = {'apiKey': apikey, 'all' :'false'}
    json = requests.get(api, params = query_params).json()
    keys = []
    for sport in json:
        keys.append(sport['key'])
    return keys

def uploadMLodds(sport_key, api_endpoint,  apikey):
    json = requests.get(api_endpoint+sport_key+'/odds/', params = {'apiKey':apikey,'regions':'us','markets':'h2h'}).json()
    get_db()
    mybooks = current_app.config['MY_BOOKS'].split(',')
    for game in json:
        game_id = game['id']
        home_team = game['home_team']
        away_team = game['away_team']
        start_time = datetime.datetime.fromisoformat(game['commence_time'][:-1]+'+00:00') #utc start_time 
        bookies = game['bookmakers']
        for book in bookies:
            book_name = book['title']
            if book_name not in mybooks:
                continue
            outcomes = book['markets'][0]['outcomes']
            for outcome in outcomes:
                cur_team = outcome['name']
                cur_price = outcome['price']
                if cur_team == home_team:
                    ht_price = cur_price
                if cur_team == away_team:
                    at_price = cur_price
            
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            if utc_now < start_time and not check_for_ml_dups(game_id,ht_price,at_price,book_name):
                g.cursor.execute('DELETE from moneyline where id = \'{}\' and book = \'{}\''.format(game_id,book_name))
                ls_commencetime =  game['commence_time'].split('T')
                start_time_str = ls_commencetime[0] + ' ' + ls_commencetime[1][:-1]
                utc_now_str = utc_now.strftime('%Y-%m-%d %H:%M:%S')
                g.cursor.execute('INSERT into moneyline VALUES (\'{}\',\'{}\',\'{}\',{},\'{}\',{},\'{}\',\'{}\',\'{}\')'.format(game_id,sport_key,home_team,ht_price,away_team, at_price, book_name, start_time_str, utc_now_str))

def uploadSpreads(sport_key, api_endpoint, apikey):
    json = requests.get(api_endpoint+sport_key+'/odds/', params = {'apiKey':apikey,'regions':'us','markets':'spreads'}).json()
    get_db()
    mybooks = current_app.config['MY_BOOKS'].split(',')
    for game in json:
        id = game['id']
        start_time = datetime.datetime.fromisoformat(game['commence_time'][:-1]+'+00:00')
        ht = game['home_team']
        at = game['away_team']
        for bookie in game['bookmakers']:
            book = bookie['title']
            if book not in mybooks:
                continue
            outcomes = bookie['markets'][0]['outcomes']
            for outcome in outcomes:
                if outcome['name']==at:
                    away_spread = outcome['point']
                    away_price = outcome['price']
                elif outcome['name']==ht:
                    home_spread = outcome['point']
                    home_price  = outcome['price']
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            if utc_now < start_time and not check_for_sp_dups(id,home_spread,home_price,away_spread,away_price,book):
                g.cursor.execute('DELETE from spreads where id = \'{}\' and book = \'{}\''.format(id,book))
                ls_commencetime =  game['commence_time'].split('T')
                start_time_str = ls_commencetime[0] + ' ' + ls_commencetime[1][:-1]
                utc_now_str = utc_now.strftime('%Y-%m-%d %H:%M:%S')
                g.cursor.execute('INSERT into spreads VALUES (\'{}\',\'{}\',\'{}\',{},{},\'{}\',{},{},\'{}\',\'{}\',\'{}\')'.format(id,sport_key,ht,home_spread,home_price,at,away_spread,away_price,book, start_time_str, utc_now_str)) 

def check_for_sp_dups(game_id, home_spread, home_price, away_spread, away_price,book):
    query = 'select Home_Team_Spread, Away_Team_Spread, Home_Team_Odds, Away_Team_Odds from spreads where id = \'{}\' and book = \'{}\''.format(game_id,book)
    g.cursor.execute(query)
    data = g.cursor.fetchall()
    if data is None:
        return False #no dups
    elif len(data) == 0:
        return False #no dups
    else:
        for row in data:
            existing_home_spread = float(row[0])
            existing_away_spread = float(row[1])
            existing_home_odds = float(row[2])
            existing_away_odds = float(row[3])
            if existing_home_spread == float(home_spread):
                if existing_away_spread == float(away_spread):
                    if abs(float(home_price)-existing_home_odds)/existing_home_odds < .01:
                        if abs(float(away_price)-existing_away_odds)/existing_away_odds < .01:
                            return True
            return False


def check_for_ml_dups(game_id, ht_price, at_price, book):
    query = 'select Home_Team_Dec_Odds, Away_Team_Dec_Odds from moneyline where id = \'{}\' and book = \'{}\''.format(game_id,book)
    g.cursor.execute(query)
    data = g.cursor.fetchall()
    if data is None:
        return False #no dups
    elif len(data) == 0:
        return False #no dups
    else:
        for row in data:
            existing_ht_price = float(row[0])
            existing_at_price = float(row[1])
            if abs(float(ht_price)-existing_ht_price)/existing_ht_price < .01:
                if abs(float(at_price)-existing_at_price)/existing_at_price < .01:
                    return True
            return False
    

def deleteSpreads():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    utc_now_str = utc_now.strftime('%Y-%m-%d %H:%M:%S')
    query = 'DELETE from spreads where TIMESTAMPADD(DAY,4,Start_Time) < \'{}\''.format(utc_now_str)
    g.cursor.execute(query)

def deleteML():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    utc_now_str = utc_now.strftime('%Y-%m-%d %H:%M:%S')
    query = 'DELETE from moneyline where TIMESTAMPADD(DAY,4,Start_Time) < \'{}\''.format(utc_now_str)
    g.cursor.execute(query)


def getIdsScoresTbl():
    g.cursor.execute('select id from scores')
    rows = g.cursor.fetchall()
    ls = []
    for row in rows:
        ls.append(row[0])
    return ls
    

def uploadScores():
    #gets the ids and sportkeys of games I've bet on; loops thru sportkeys and retrieves scores for each sport; for each sport, loops thru completed games 
    #, checks that we bet on this game and that the game is not already in the score table, and then queries the bets we made on the game and updates  
    # the balances accordingly; it also uploads the score to a score table;
    # this function runs each time that the user logs in
    username = session.get('user_id')
    spread_ids = []
    ml_ids = []
    bet_on_ids = []
    bet_on_sportkeys = []
    g.cursor.execute('SELECT id, sportkey from ml_bets where username = \'{}\' and settled = 0'.format(username))
    rows = g.cursor.fetchall()
    for row in rows:
        if row[0] not in ml_ids:
            ml_ids.append(row[0])
        if row[1] not in bet_on_sportkeys:
            bet_on_sportkeys.append(row[1])
    g.cursor.execute('SELECT id, sportkey from spread_bets where username = \'{}\' and settled = 0'.format(username))
    rows = g.cursor.fetchall()
    for row in rows:
        if row[0] not in spread_ids:
            spread_ids.append(row[0])
        if row[1] not in bet_on_sportkeys:
            bet_on_sportkeys.append(row[1])

    score_ids = getIdsScoresTbl()
    bet_on_ids = set(ml_ids).union(spread_ids) #games bet on by user that have not been settled yet

    for key in bet_on_sportkeys:
        json = requests.get(current_app.config['API']+key+'/scores/',params={'apiKey':current_app.config['APIKEY'],'daysFrom':3}).json()
        ht = ''
        at = ''
        ht_score = -1
        at_score = -1
        for game in json:
            if game['completed'] and (game['id'] in bet_on_ids):
                scores = game['scores']
                for score in scores:
                    cur_team = score['name']
                    cur_score = score['score']
                    if cur_team == game['home_team']:
                        ht = cur_team
                        ht_score = float(cur_score)
                    elif cur_team == game['away_team']:
                        at = cur_team
                        at_score = float(cur_score)
                if game['id'] in spread_ids:
                    g.cursor.execute('select * from spread_bets where id = \'{}\' and username = \'{}\' and settled = 0'.format(game['id'],username))
                    rows = g.cursor.fetchall()
                    processSpreadBetResults(rows, ht, ht_score, at, at_score)
                    settleBets(rows,'sp')
                if game['id'] in ml_ids:
                    g.cursor.execute('select * from ml_bets where id = \'{}\' and username = \'{}\' and settled = 0'.format(game['id'],username))
                    rows = g.cursor.fetchall()
                    processMLBetResults(rows,ht,ht_score,at,at_score)
                    settleBets(rows, 'ml')
                if game['id'] not in score_ids:
                    g.cursor.execute('INSERT INTO scores VALUES (\'{}\',\'{}\',{},\'{}\',{})'.format(game['id'],ht,ht_score,at,at_score))

def settleBets(data, type_of_bet):
    if type_of_bet == 'ml':
        for row in data:
            id = row[0]
            username = session.get('user_id')
            g.cursor.execute('UPDATE ml_bets SET settled = 1 WHERE id = \'{}\' and username = \'{}\''.format(id,username))
    else:
        for row in data:
            id = row[0]
            username = session.get('user_id')
            g.cursor.execute('UPDATE spread_bets SET settled = 1 WHERE id = \'{}\' and username = \'{}\''.format(id,username))


def processMLBetResults(ls,ht,hts,at,ats):
    for row in ls:
        team_bet_on = row[2]
        book = row[3]
        amt = float(row[4])
        odds = float(row[5])
        if team_bet_on == ht:
            if hts > ats:
                #won bet
                payout = amt * odds
                updateBalance(book,payout)
        elif team_bet_on == at:
            if ats > hts:
                payout = amt * odds
                updateBalance(book,payout)

def processSpreadBetResults(ls, ht, hts, at, ats):
    # spread_bets (id VARCHAR(100), sportkey VARCHAR(100),team_bet_on VARCHAR(100), book_bet_at VARCHAR(100), amount_bet FLOAT(7,2), spread_offered FLOAT(7,2), line_offered FLOAT(7,2), CONSTRAINT id_book_team PRIMARY KEY (id,team_bet_on,book_bet_at))')

    for row in ls:
        team_bet_on = row[2]
        book = row[3]
        amt = float(row[4])
        spread = float(row[5])
        price = float(row[6])

        if team_bet_on == ht:
            if spread > 0:
                if ats-hts < spread:
                    #won bet!
                    payout = amt * price 
                    updateBalance(book,payout)
            elif spread < 0:
                spread = -1*spread
                if hts - ats > spread:
                    #won bet
                    payout = amt * price 
                    updateBalance(book,payout)
        elif team_bet_on == at:
            if spread > 0:
                if hts-ats < spread:
                    #won bet!
                    payout = amt * price 
                    updateBalance(book,payout)
            elif spread < 0:
                spread = -1*spread
                if ats - hts > spread:
                    #won bet
                    payout = amt * price 
                    updateBalance(book,payout)

def updateBalance(book, amount):
    g.cursor.execute('select amount from balance where book = \'{}\' and  username = \'{}\''.format(book, session.get('user_id')))
    row = g.cursor.fetchall()
    cur_amt = float(row[0][0])
    new_amt = cur_amt + amount
    g.cursor.execute('update balance set amount = {} where book = \'{}\' and username = \'{}\''.format(new_amt,book,session.get('user_id')))

def reformatSpreadsQueryResult(rows):
    spread_dict = {}
    for row in rows:
        id = row[0]
        if id in spread_dict:
            #game in dict
            bookie_dict = spread_dict[id][3]
            book = row[8]
            bookie_dict[book] = {'ht_spread':float(row[3]), 'ht_line': float(row[4]), 'at_spread': float(row[6]), 'at_line':float(row[7])}
        else:
            #game not in dict
            ht = row[2]
            at = row[5]
            book = row[8]
            start = row[9]
            bookie_dict = {}
            l = [ht,at,start,bookie_dict]
            bookie_dict[book] = {'ht_spread':float(row[3]), 'ht_line': float(row[4]), 'at_spread': float(row[6]), 'at_line':float(row[7])}
            spread_dict[id] = l
    return spread_dict

def reformatMLQueryResult(rows):
    ml_dict = {}
    for row in rows:
        id = row[0]
        if id in ml_dict:
            #game in dict
            bookie_dict = ml_dict[id][3]
            bookie_dict[row[6]] = {'ht_line': float(row[3]), 'at_line':float(row[5])}
        else:
            #game not in dict
            ht  = row[2]
            at = row[4]
            start = row[7]
            bookie_dict = {}
            l = [ht,at,start,bookie_dict]
            bookie_dict[row[6]] = {'ht_line': float(row[3]), 'at_line':float(row[5])}
            ml_dict[id] = l
    return ml_dict

def reformatSettledBets(settled_ml, settled_sp):
    settled = {}
    #settled
        #game id
            #ml
                #list of dicts
            #sp
                #list of dicts
            #score
                #dict
    
    for row in settled_ml:
        id = row[0]
        bet_on = row[2]
        book = row[3]
        line = row[5]
        amt = row[4]
        if id in settled and 'ml' in settled[id]:
            #processed a  ml bet on this game before
            settled[id]['ml'].append({'bet_on': bet_on, 'book': book, 'line': line, 'amt':amt})
        elif id in settled:
            #first ml bet on this game but have bet spread
            settled[id]['ml']=  [{'bet_on': bet_on, 'book': book, 'line': line, 'amt':amt}]
        else:
            #have not processed a bet on this game before
            settled[id] =  {}
            settled[id]['ml']=  [{'bet_on': bet_on, 'book': book, 'line': line, 'amt':amt}]

    for row in settled_sp:
        # id VARCHAR(100), sportkey VARCHAR(100),team_bet_on VARCHAR(100), book_bet_at VARCHAR(100), amount_bet FLOAT(7,2), spread_offered FLOAT(7,2), line_offered FLOAT(7,2), username VARCHAR(100), settled INT, CONSTRAINT id_book_team_user PRIMARY KEY (id,team_bet_on,book_bet_at, username))')
        id = row[0]
        bet_on = row[2]
        book = row[3]
        amt = row[4]
        spread = row[5]
        line = row[6]
        if id in settled and 'sp' in settled[id]:
            settled[id]['sp'].append({'bet_on': bet_on, 'book': book, 'spread': spread, 'line': line, 'amt':amt})
        elif id in settled:
            settled[id]['sp'] = [{'bet_on': bet_on, 'book': book, 'spread': spread, 'line': line, 'amt':amt}]
        else:
            settled[id] = {}
            settled[id]['sp'] = [{'bet_on': bet_on, 'book': book, 'spread': spread, 'line': line, 'amt':amt}]

    
    
    for id in settled.keys():
        #scores (id VARCHAR(100), Home_Team VARCHAR(100), Home_Team_Score FLOAT(7,2), Away_Team VARCHAR(100), Away_Team_Score  FLOAT(7,2),  PRIMARY KEY (id))')
        g.cursor.execute('select * from scores where id = \'{}\''.format(id))
        rows = g.cursor.fetchall()
        row = rows[0]
        ht = row[1]
        hts = row[2]
        at = row[3]
        ats = row[4]
        settled[id]['score'] = {'ht':ht,'hts':hts,'at':at,'ats':ats}
    
    return settled

def reformatUnsettledBets(nonsettled_ml,nonsettled_sp):
    nonsettled = {}
    #settled
        #game id
            #ml
                #list of dicts
            #sp
                #list of dicts
            #score
                #dict
    
    
    #nonsettled
        #game id
            #ml
                #list of dicts
            #sp
                #list of dicts
    
    for row in nonsettled_ml:
        id = row[0]
        bet_on = row[2]
        book = row[3]
        line = row[5]
        amt = row[4]
        if id in nonsettled and 'ml' in nonsettled[id]:
            #processed a bet on this game before
            nonsettled[id]['ml'].append({'bet_on': bet_on, 'book': book, 'line': line, 'amt':amt})
        elif id in nonsettled:
            nonsettled[id]['ml']=  [{'bet_on': bet_on, 'book': book, 'line': line, 'amt':amt}]
        else:
            #have not processed a bet on this game before
            nonsettled[id] =  {}
            nonsettled[id]['ml']=  [{'bet_on': bet_on, 'book': book, 'line': line, 'amt':amt}]
    
    for row in nonsettled_sp:
        id = row[0]
        bet_on = row[2]
        book = row[3]
        amt = row[4]
        spread = row[5]
        line = row[6]
        if id in nonsettled and 'sp' in nonsettled[id]:
            nonsettled[id]['sp'].append({'bet_on': bet_on, 'book': book, 'spread': spread, 'line': line, 'amt':amt})
        elif id in nonsettled:
            nonsettled[id]['sp'] = [{'bet_on': bet_on, 'book': book, 'spread': spread, 'line': line, 'amt':amt}]
        else:
            nonsettled[id] = {}
            nonsettled[id]['sp'] = [{'bet_on': bet_on, 'book': book, 'spread': spread, 'line': line, 'amt':amt}]
    
    
    return nonsettled


