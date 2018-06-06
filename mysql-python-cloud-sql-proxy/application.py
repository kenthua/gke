import os
import flask
import MySQLdb

application = flask.Flask(__name__)
application.debug = True

@application.route('/')
def serve():
  storage = Storage()
  storage.populate()
  name = storage.name()
  return "Hello World, %s!" % (name)

class Storage():
  def __init__(self):
    self.db = MySQLdb.connect(
      user   = os.getenv('MYSQL_USERNAME'),
      passwd = os.getenv('MYSQL_PASSWORD'),
      db     = os.getenv('MYSQL_DB_NAME'),
      host   = os.getenv('MYSQL_HOSTNAME'),
      port   = int(os.getenv('MYSQL_HOST_PORT'))
    )

    cur = self.db.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS names(name VARCHAR(10))")

  def populate(self):
    cur = self.db.cursor()
    cur.execute("INSERT INTO names(name) VALUES('Johnny')")

  def name(self):
    cur = self.db.cursor()
    cur.execute("SELECT * FROM names")
    row = cur.fetchone()
    return row[0]

if __name__ == "__main__":
  application.run(host='0.0.0.0', port=5000)
