###
# Copyright (c) 2010, melodeath
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import sqlite3 as sqlite
import random

import supybot.conf as conf
import supybot.utils as utils
import supybot.ircdb as ircdb
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

QUOTE_NOT_FOUND = 'There are no QuoteX quotes matching your criteria.'
QUOTE_DB_EMPTY = 'QuoteX database is empty.'
QUOTE_ADDED = 'QuoteX has been added successfully.'
QUOTE_NOT_ADDED = 'QuoteX has not been added successfully.'
QUOTE_DELETED = 'QuoteX has been deleted successfully.'
QUOTE_NOT_DELETED = 'QuoteX has not been deleted successfully.'
QUOTE_NOT_CHANGED = 'QuoteX has not been changed successfully.'
QUOTE_ID_NOT_FOUND = 'No QuoteX quote with this id.'

def check_identify(user, capability):
    try:
        u = ircdb.users.getUser(user)
    except KeyError:
        pass
    else:
        if u._checkCapability(capability):
            return True
    return False
    
def identify(capability):
    def wrap(f):
        def wrapped_f(*args, **kwargs):
            """
            Testing docstring.
            """
            if check_identify(args[2].nick, capability):
                return f(*args, **kwargs)
            return args[1].error(conf.supybot.replies.incorrectAuthentication(), Raise=True) 
        return wrapped_f
    return wrap

class QuoteX(callbacks.Plugin):
    """Simple quotex database."""

    def __init__(self, irc):
        self.__parent = super(QuoteX, self)
        self.__parent.__init__(irc)
        self.conn = sqlite.connect(self.registryValue('dbName'), check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()

    def to_unicode(self, string, encodings = ['utf-8', 'cp1250']):
        if isinstance(string, str):
            if not isinstance(string, str):
                for encoding in encodings:
                    try:
                        string = str(string, encoding)
                    except UnicodeError:
                        pass
                    else:
                        break
        return string

    def from_unicode(self, string, encodings = ['utf-8', 'cp1250']):
        for encoding in encodings:
            try:
                string = string.encode(encoding)
            except UnicodeError:
                pass
            else:
                break
        return string

    def create_table(self):
        return self.cursor.execute('CREATE TABLE IF NOT EXISTS quotex (id INTEGER PRIMARY KEY,text TEXT)')

    def format_quotex(self, quotex):
        return '#%s: %s' % (quotex[0], quotex[1])

    def list_random(self, l):
        return l.pop(random.randrange(len(l)))

    def get_quotex(self, id):
        id = int(id)
        if self.cursor.execute('SELECT id,text FROM quotex WHERE id LIKE (?) LIMIT 1', (id,)):
            row = self.cursor.fetchone()
            if row:
                return self.format_quotex(row)
        return QUOTE_ID_NOT_FOUND

    def get_random_quotex(self):
        if self.cursor.execute('SELECT id,text FROM quotex ORDER BY RANDOM() LIMIT 1'):
            row = self.cursor.fetchone()
            if row:
                return self.format_quotex(row)
        return QUOTE_DB_EMPTY

    def search_quotex(self, search):
        search = '%' + self.to_unicode(search) + '%'
        if self.cursor.execute('SELECT id,text FROM quotex WHERE text LIKE (?) COLLATE NOACCENTS', (search,)):
            result = self.cursor.fetchall()
            count = len(result)
            if count == 1:
                return self.format_quotex(result[0])
            elif count > 1:
                return self.format_quotex(self.list_random(result))
        return QUOTE_NOT_FOUND

       
    def addquotex(self, irc, msg, args, text):
        """
        <text> Adds new quotex.
        """
        text = self.to_unicode(text)
        if self.cursor.execute('INSERT INTO quotex VALUES (NULL, ?)', (text,)):
            self.cursor.execute('UPDATE quotex SET id = rowid;')
            self.conn.commit()
            irc.reply(QUOTE_ADDED) 
        else:
            irc.reply(QUOTE_NOT_ADDED)
    addquotex = wrap(addquotex, ['text'])

    def changequotex(self, irc, msg, args, id_, text):
        """
        <id> Changes quotex by id.
        """
        text = self.to_unicode(text)
        if (self.cursor.execute('UPDATE quotex SET text = ? WHERE id = ?', (text, id_,))):
             self.conn.commit()
             irc.reply('QuoteX #%d has been updated successfully.' % id_)
        else:
             irc.reply(QUOTE_NOT_CHANGED)
    changequotex = wrap(changequotex, ['int', 'text'])

#   @identify("owner")
    def delquotex(self, irc, msg, args, id):
        """
        <id> Deletes quotex by id.
        """
        id = int(id)
        if self.cursor.execute('DELETE FROM quotex WHERE id = (?)', (id,)):
            self.cursor.executescript('CREATE TABLE tmp_tbl AS SELECT id, text FROM quotex; UPDATE tmp_tbl SET id=rowid; DROP TABLE quotex; CREATE TABLE quotex AS SELECT id, text FROM tmp_tbl; DROP TABLE tmp_tbl;') 
            self.conn.commit()
            irc.reply(QUOTE_DELETED)
        else:
            irc.reply(QUOTE_NOT_DELETED)
    delquotex = wrap(delquotex, ['int'])

    def quotex(self, irc, msg, args, text):
        """
        <text> Searches quotex by id or by text query. Returns random quotex by default.
        """
        if not text:
            irc.reply(self.get_random_quotex())
            return
        try:
            int(text)
        except ValueError:
            irc.reply(self.search_quotex(text))
        else:
            irc.reply(self.get_quotex(text))
    quotex = wrap(quotex, [additional('text')])
    
    def quotexstats(self, irc, msg, args):
        """
        Returns database stats.
        """
        if self.cursor.execute('SELECT count(*) as cnt FROM quotex'):
            row = self.cursor.fetchone()
            irc.reply('QuoteX stats: %s' % row[0])
            return
        irc.reply(QUOTE_DB_EMPTY)
    quotexstats = wrap(quotexstats)
        
    def lastquotex(self, irc, msg, args):
        """
        Returns the last quotex.
        """
        if self.cursor.execute('SELECT id,text FROM quotex ORDER BY id DESC LIMIT 1'):
            row = self.cursor.fetchone()
            irc.reply(self.format_quotex(row))
            return
        irc.reply(QUOTE_DB_EMPTY)
    lastquotex = wrap(lastquotex)

Class = QuoteX

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
