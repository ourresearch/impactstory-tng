angular.module('currentUser', [
])



    .factory("CurrentUser", function($auth, $http, $q, $route){


        var sendTokenToIntercom = function(){
            // do send to intercom stuff
        }

        var load = function(token){
            if (token){
                $auth.setToken(token)
                sendTokenToIntercom()
            }
            else {
                // load the current user from the server.
            }
        }

        return {
            load: load
        }
    })