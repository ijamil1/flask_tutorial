from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, current_app, session
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.helper_funcs import get_db, get_inseason_sports, uploadMLodds, uploadSpreads, deleteML, deleteSpreads,uploadScores, reformatMLQueryResult, reformatSpreadsQueryResult, reformatBets
import datetime

bp = Blueprint('bets', __name__)


@bp.route('/home', methods = ('GET', 'POST'))
@login_required
def index():
    if request.method == 'GET':
        get_db()
        #this block deletes games from spreads and moneyline table which have already occurred
        deleteSpreads()  
        deleteML()
        #
        uploadScores()
        return render_template('home.html')
    elif request.method == 'POST':
        if request.form.get('button') == 'Spreads':
            return redirect(url_for('bets.get_spreads'))
        elif request.form.get('button') == 'Moneylines':
            return redirect(url_for('bets.get_ml'))
        else:
            return redirect(url_for('bets.index'))
    else:
        return redirect(url_for('bets.index'))

@bp.route('/get_spreads', methods=('GET', 'POST'))
@bp.route('/get_spreads/<sport>', methods=('GET', 'POST'))
@login_required
def get_spreads(sport=None):
    if sport:
        #not none, so display moneylines for the sports
        get_db()
        g.cursor.execute('SELECT * FROM spreads WHERE sport_key = \'{}\' and Start_Time > \'{}\''.format(sport,datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')))
        rows = g.cursor.fetchall()
        return render_template('bets/display_sp2.html', data=reformatSpreadsQueryResult(rows))

    else:
        #sport is none
        if request.method == 'POST':
            sportkey = request.form.get('sportkeys')
            in_seasons_keys = get_inseason_sports()

            error = None

            if not sportkey:
                error = 'Sport key is required.'
            if sportkey not in in_seasons_keys:
                error = 'invalid  sportkey'
            if error is not None:
                flash(error)
            else:
                uploadSpreads(sportkey,current_app.config['API'],current_app.config['APIKEY'])
                return redirect(url_for('.get_spreads',sport=sportkey))
        return render_template('bets/submit_sport.html', data=get_inseason_sports())

@bp.route('/get_moneylines', methods=('GET', 'POST'))
@bp.route('/get_moneylines/<sport>', methods=('GET', 'POST'))
@login_required
def get_ml(sport=None):
    if sport:
        #not none, so display moneylines for the sports
        get_db()
        g.cursor.execute('SELECT * FROM moneyline WHERE sport_key = \'{}\' and Start_Time > \'{}\''.format(sport,datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')))
        rows = g.cursor.fetchall()
        return render_template('bets/display_ml2.html', data=reformatMLQueryResult(rows))

    else:
        #sport is none
        if request.method == 'POST':
            sportkey = request.form.get('sportkeys')
            in_seasons_keys = get_inseason_sports()

            error = None

            if not sportkey:
                error = 'Sport key is required.'
            if sportkey not in in_seasons_keys:
                error = 'invalid  sportkey'

            if error is not None:
                flash(error)
            else:
                uploadMLodds(sportkey,current_app.config['API'],current_app.config['APIKEY'])
                return redirect(url_for('.get_ml',sport=sportkey))

        return render_template('bets/submit_sport.html', data=get_inseason_sports())


@bp.route('/Balances', methods = ('GET', 'POST'))
@login_required
def add_get_Balance():
    get_db()
    if request.method == 'GET':
        g.cursor.execute('select book, amount from balance where username = \'{}\''.format(session.get('user_id')))
        return render_template('bets/balance.html',data={'mybooks': current_app.config['MY_BOOKS'], 'results':g.cursor.fetchall()})
    else:
        #post
        book = request.form.get('book')
        amount = float(request.form.get('amount'))
        g.cursor.execute('select * from balance where username = \'{}\' and book = \'{}\''.format(session.get('user_id'),book))
        rows = g.cursor.fetchall()
        if len(rows) > 0:
            #update book
            g.cursor.execute('UPDATE balance SET amount = {} WHERE username = \'{}\' and book = \'{}\''.format(amount+rows[0][2],session.get('user_id'),book))
        else:
            #insert book
            g.cursor.execute('INSERT into balance VALUES (\'{}\',\'{}\',{})'.format(session.get('user_id'),book,amount))
        return redirect(url_for('bets.add_get_Balance'))

@bp.route('/getBets', methods = ('GET','POST'))
@login_required
def getBets():
    username = session.get('user_id')
    get_db()
    g.cursor.execute('select * from spread_bets where username = \'{}\' and settled = 1'.format(username))
    settled_sp_bets_rows = g.cursor.fetchall()
    g.cursor.execute('select * from spread_bets where username = \'{}\' and settled = 0'.format(username))
    nonsettled_sp_bets_rows = g.cursor.fetchall()
    g.cursor.execute('select * from ml_bets where username = \'{}\' and settled = 1'.format(username))
    settled_ml_bets_rows = g.cursor.fetchall()
    g.cursor.execute('select * from ml_bets where username = \'{}\' and settled = 0'.format(username))
    nonsettled_ml_bets_rows = g.cursor.fetchall()
    d = reformatBets(settled_ml_bets_rows, settled_sp_bets_rows,nonsettled_ml_bets_rows,nonsettled_sp_bets_rows)
    return render_template('bets/display_bets.html', data=d)

# data
    #nonsettled
            #game id
                #ml
                    #list of dicts
                #sp
                    #list of dicts
    #settled
            #game id
                #ml
                    #list of dicts
                #sp
                    #list of dicts
                #score
                    #dict

@bp.route('/ml_bet/<id>', methods = ('GET','POST'))
@login_required
def makeBet_ml(id=None):
    if id is None:
        return redirect(url_for('bets.get_ml'))
    get_db()
    if request.method == 'GET':
        g.cursor.execute('SELECT * FROM moneyline WHERE id = \'{}\''.format(id))
        rows = g.cursor.fetchall()
        data = reformatMLQueryResult(rows)
        mybooks_str = current_app.config['MY_BOOKS']
        mybooks_list = mybooks_str.split(',')
        data['books']=mybooks_list
        data['id'] = id
        d = data
        return render_template('bets/display_game_ml.html', data=d)
    else:
        #post
        book =  request.form.get('books')
        team = request.form.get('team')
        amt = float(request.form.get('amount'))
        username = session.get('user_id')
        g.cursor.execute('select amount from balance where book = \'{}\' and username = \'{}\''.format(book,username))
        cur_amt = float(g.cursor.fetchall()[0][0])
        if amt > cur_amt :
            #not enough money
            return redirect(url_for('bets.makeBet_ml',id=id))
        else:
            g.cursor.execute('UPDATE balance set amount = {} where book = \'{}\' and username = \'{}\''.format(cur_amt-amt,book,username))  

        g.cursor.execute('select * from ml_bets where id = \'{}\' and team_bet_on = \'{}\' and book_bet_at = \'{}\' and username = \'{}\''.format(id,team,book,username))
        rows = g.cursor.fetchall()
        if rows is None or len(rows) == 0:
            #haven't bet on this yet
            g.cursor.execute('select sport_key, Home_Team, Home_Team_Dec_Odds, Away_Team_Dec_Odds from moneyline where id = \'{}\' and book = \'{}\''.format(id,book))
            ml_row = g.cursor.fetchall()[0]
            sportkey = ml_row[0]
            if team == ml_row[1]:
                #home team
                g.cursor.execute('INSERT into ml_bets VALUES (\'{}\',\'{}\',\'{}\',\'{}\',{},{},\'{}\',0)'.format(id,sportkey,team,book,amt,ml_row[2],username))
            else:
                #away team
                g.cursor.execute('INSERT into ml_bets VALUES (\'{}\',\'{}\',\'{}\',\'{}\',{},{},\'{}\',0)'.format(id,sportkey,team,book,amt,ml_row[3],username))
            return redirect(url_for('bets.getBets'))
        else:
            return redirect('bets.get_ml',sport=rows[0][1])
        

@bp.route('/sp_bet/<id>', methods = ('GET','POST'))
@login_required
def makeBet_sp(id=None):
    if id is None:
        return redirect(url_for('bets.get_spreads'))
    if request.method == 'GET':
        get_db()
        g.cursor.execute('SELECT * FROM spreads WHERE id = \'{}\''.format(id))
        rows = g.cursor.fetchall()
        data = reformatSpreadsQueryResult(rows)
        mybooks_str = current_app.config['MY_BOOKS']
        mybooks_list = mybooks_str.split(',')
        data['books']=mybooks_list
        data['id'] = id
        d = data
        return render_template('bets/display_game_sp.html', data=d)
    else:
        #post
        book =  request.form.get('books')
        team = request.form.get('team')
        amt = request.form.get('amount')
        username = session.get('user_id')
        g.cursor.execute('select amount from balance where book = \'{}\' and username = \'{}\''.format(book,username))
        cur_amt = float(g.cursor.fetchall()[0][0])
        if amt > cur_amt :
            #not enough money
            return redirect(url_for('bets.makeBet_ml',id=id))
        else:
            g.cursor.execute('UPDATE balance set amount = {} where book = \'{}\' and username = \'{}\''.format(cur_amt-amt,book,username))  

        g.cursor.execute('select * from spread_bets where id = \'{}\' and team_bet_on = \'{}\' and book_bet_at = \'{}\' and username = \'{}\''.format(id,team,book,username))
        rows = g.cursor.fetchall()
        if rows is None or len(rows) == 0:
            #haven't bet on this yet
            g.cursor.execute('select sport_key, Home_Team, Home_Team_Spread, Home_Team_Odds, Away_Team_Spread, Away_Team_Odds from spreads where id = \'{}\' and book = \'{}\''.format(id,book))
            sp_row = g.cursor.fetchall()[0]
            sportkey = sp_row[0]
            if team == sp_row[1]:
                #home team
                g.cursor.execute('INSERT into spread_bets VALUES (\'{}\',\'{}\',\'{}\',\'{}\',{},{},{},\'{}\',0)'.format(id,sportkey,team,book,amt,sp_row[2],sp_row[3],username))
            else:
                #away team
                g.cursor.execute('INSERT into spread_bets VALUES (\'{}\',\'{}\',\'{}\',\'{}\',{},{},{},\'{}\',0)'.format(id,sportkey,team,book,amt,sp_row[4],sp_row[5],username))
            return redirect(url_for('bets.getBets'))
        else:
            return redirect('bets.get_ml',sport=rows[0][1])
