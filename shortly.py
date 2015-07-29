
import os
import redis
import urlparse

from werkzeug.wrappers      import Request, Response
from werkzeug.routing       import Map, Rule
from werkzeug.exceptions    import HTTPException, NotFound
from werkzeug.wsgi          import SharedDataMiddleware
from werkzeug.utils         import redirect

from jinja2 import Environment, FileSystemLoader

def IsValidUrl( url ):
    parts = urlparse.urlparse( url )
    return parts.scheme in ( "http", "https" )

def Base36_Encode( number ):
    assert number >= 0, "positive integer required"
    if number == 0:
        return "0"
    base36 = []
    while number != 0:
        number, i = divmod( number, 36 )
        base36.append( "0123456789abcdefghijklnopqrstuvwxyz"[ i ] )
    return "".join( reversed( base36 ) )

class AShortly( object ):
    def __init__( self, config ):
        self.redis      = redis.Redis( host=config[ "redis_host" ], port=config[ "redis_port" ] )
        template_path   = os.path.join( os.path.dirname( __file__ ), "templates" )
        self.jinja_env  = Environment(
            loader=FileSystemLoader( template_path ),
            autoescape=True
        )
        rules           = [
            Rule( "/", endpoint="NewUrl" ),
            Rule( "/<short_id>", endpoint="FollowShortLink" ),
            Rule( "/<short_id>+", endpoint="ShortLinkDetails" ),
        ]
        self.url_map    = Map( rules )


    def InsertUrl( self, url ):
        short_id = self.redis.get( "reverse-url:" + url )
        if short_id is not None:
            return short_id
        else:
            url_num     = self.redis.incr( "last-url-id" )
            short_id    = Base36_Encode( url_num )
            self.redis.set( "url-target:" + short_id, url )
            self.redis.set( "reverse-url:" + url, short_id )
            return short_id


    def RenderTemplate( self, template_name, **context ):
        t = self.jinja_env.get_template( template_name )
        return Response( t.render( context ), mimetype="text/html" )

    def DispatchRequest( self, request ):
        adapter = self.url_map.bind_to_environ( request.environ )
        try:
            endpoint, values = adapter.match()
            return getattr( self, "On" + endpoint )( request, **values )
        except HTTPException, e:
            return e

    def OnNewUrl( self, request ):
        error = None
        url = ""
        if request.method == "POST":
            url = request.form[ "url" ]
            if not IsValidUrl( url ):
                error = "Please enter a valid URL"
            else:
                short_id = self.InsertUrl( url )
                return redirect( "/%s+" % short_id )
        return self.RenderTemplate( "new_url.html", error=error, url=url )

    def OnFollowShortLink( self, request, short_id ):
        link_target = self.redis.get( "url-target:" + short_id )
        if link_target is None:
            raise NotFound()
        self.redis.incr( "click-count:" + short_id )
        return redirect( link_target )

    def OnShortLinkDetails( self, request, short_id ):
        link_target = self.redis.get( "url-target:" + short_id )
        if link_target is None:
            raise NotFound()
        click_count = int( self.redis.get( "click-count:" + short_id ) or 0 )
        return self.RenderTemplate(
            "short_link_details.html",
            link_target=link_target,
            short_id=short_id,
            click_count=click_count,
        )

    def WsgiApp( self, environ, start_response ):
        request     = Request( environ )
        response    = self.DispatchRequest( request )
        return response( environ, start_response )

    def __call__( self, environ, start_response ):
        return self.WsgiApp( environ, start_response )

def CreateApp( redis_host="127.0.0.1", redis_port=6379, with_static=True ):
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
