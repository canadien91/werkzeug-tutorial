
import os
import redis
import urlparse

from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.wsgi import SharedDataMiddleware
from werkzeug.utils import redirect

from jinja2 import Environment, FileSystemLoader

class AShortly( object ):
    def __init__( self, config ):
        self.redis = redis.Redis( config[ "redis_host" ], config[ "redis_port" ] )

    def DispatchRequest( self, request ):
        return Response( "Hello World" )

    def WsgiApp( self, environ, start_response ):
        request     = Request( environ )
        response    = self.DispatchRequest( request )
        return response( environ, start_response )

    def __call__( self, environ, start_response ):
        return self.WsgiApp( environ, start_response )

def CreateApp( redis_host="localhost", redis_port=6543, with_static=True ):
    config = {
        "redis_host": redis_host,
        "redis_port": redis_port,
    }
    app = AShortly( config )
    if with_static:
        app.WsgiApp = SharedDataMiddleware( app.WsgiApp, {
            "/static": os.path.join( os.path.dirname( __file__ ), "static" )
        } )
    return app

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    app = CreateApp()
    run_simple( "127.0.0.1", 5050, app, use_debugger=True, use_reloader=True )
