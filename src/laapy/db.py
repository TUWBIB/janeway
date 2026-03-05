import logging
import traceback
from abc import ABC,abstractmethod
from functools import wraps

try:
    import mariadb
except:
    pass

class LaapyDBInterface(ABC):

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def getConnection(self):
        pass

    @abstractmethod
    def beginCall(self,op,target,label,url,body,ts_begin):
        conn = self.getConnection()
        cur = conn.cursor()
        sql = "INSERT INTO api_call (op,url,body,ts_begin,label,target) VALUES (?,?,?,?,?,?)"
        try:
            cur.execute(sql,(op,url,body,ts_begin,label,target))
            conn.commit();
            return cur.lastrowid
        except mariadb.Error as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise 
        finally:
            conn.close()

    @abstractmethod
    def updateCall(self,ts_end,status_code,error_code,error_message,id):
        conn = self.getConnection()
        cur = conn.cursor()
        sql = "UPDATE api_call SET ts_end=?,status_code=?,error_code=?,error_message=? WHERE id=?"
        try:
            cur.execute(sql,(ts_end,status_code,error_code,error_message,id))
            conn.commit();
        except mariadb.Error as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise 
        finally:
            conn.close()


### obsolete decorator for simgle connections
### works, but isn't sufficient for cases, when parallel db accesses are needed

# decorator as class method dubious?
# is this even correct?
# seems to work though
# def connectionAlive(f):
#     @wraps(f)
#     def decorated_function(self,*args,**kwargs):
#         alive = False
# 
#         try:
#             self.cur.execute("SELECT 1")
#             alive = True
#         except Exception as e:
#             logging.error('connection might have died, trying to reconnect')
#             logging.error(e)
#             logging.error(traceback.format_exc())
#             try:
#                 self.disconnect()
#                 self.connect()
#                 self.cur.execute("SELECT 1")
#                 alive = True
#             except Exception as e:
#                 logging.fatal('connection has died? reconnect not successful')
#                 logging.error(e)
#                 logging.error(traceback.format_exc())
#             
#         if alive:
#             val = f(self,*args,**kwargs)
#             return val
# 
#     return decorated_function

class DB(LaapyDBInterface):
    def __init__(self,host,db,user,passwd,port,autocommit=True):
        self.host = host
        self.db = db
        self.user = user
        self.passwd = passwd
        self.port = port
        self.autocommit = autocommit

    def connect(self):
        self.pool = mariadb.ConnectionPool(
            pool_name="pool",
            pool_size=10,
            pool_reset_connection=True,
            host=self.host,
            port=int(self.port),
            user=self.user,
            passwd=self.passwd,
            db=self.db,
            autocommit=self.autocommit,
        )

    def disconnect(self):
        if self.pool:
            self.pool.close()

    # get connection from pool and check if it works
    # if not: close and replace in pool
    def getConnection(self,retrycount=0) -> mariadb.Connection:
        logging.debug("connection pool")
        logging.debug(f"connection pool free {len(self.pool._connections_free)}")
        logging.debug(f"connection pool used {len(self.pool._connections_used)}")

        if retrycount > self.pool.connection_count:
            raise Exception("really can't get connection")

        conn:mariadb.Connection = None
        
        # connection available?
        try:
            conn = self.pool.get_connection()
        except Exception as e:
            logging.error('connection pool exhausted')
            logging.error(e)
            logging.error(traceback.format_exc())
            raise e

        # check if connection works?
        try:
            cur = conn.cursor()
            cur.execute("SET NAMES utf8mb4")
        except Exception as e:
            logging.error('connection might have died, trying to replace in pool')
            logging.error(e)
            logging.error(traceback.format_exc())

            conn.close()
            self.pool._replace_connection(conn)

            retrycount +=1
            conn = self.getConnection(retrycount=retrycount)
            
        return conn        
    
    def beginCall(self,op,target,label,url,body,ts_begin):
        return super().beginCall(op,target,label,url,body,ts_begin)

    def updateCall(self,ts_end,status_code,error_code,error_message,id):
        super().updateCall(ts_end,status_code,error_code,error_message,id)
