angular.module('currentUser', [
])



    .factory("CurrentUser", function($auth, $http, $q, $route){


        var sendTokenToIntercom = function(){
            // do send to intercom stuff
        }

        var isAuthenticatedPromise = function(){
            // this is actually a synchronous method, it just returns
            //      a promise so it can be used in route definitions.
            var deferred = $q.defer()
            if ($auth.isAuthenticated()) {
                deferred.resolve()
            }
            else {
                console.log("user isn't logged in, so isAuthenticatedPromise() is rejecting promise.")
                deferred.reject()
            }
            return deferred.promise
        }


        var doTheyHaveProducts = function(){
            $http.get("/api/me").success(function(resp){

            })
        }


        var twitterAuthenticate = function (intent) {
            // send the user to twitter.com to authenticate
            // twitter will send them back to us from there.
            // @intent should be either "register" or "login".

            var redirectUri = window.location.origin + "/oauth/" + intent + "/twitter"

            console.log("authenticate with twitters!");

            // first ask our server to get the OAuth token that we use to create the
            // twitter URL that we will redirect the user too.
            var baseUrlToGetOauthTokenFromOurServer = "/api/auth/twitter/request-token?redirectUri=";
            var baseTwitterLoginPageUrl = "https://api.twitter.com/oauth/authenticate?oauth_token="
            $http.get(baseUrlToGetOauthTokenFromOurServer + redirectUri).success(
                function(resp){
                    console.log("twitter request token", resp)
                    var twitterLoginPageUrl = baseTwitterLoginPageUrl + resp.oauth_token
                    window.location = twitterLoginPageUrl
                }
            )
        };

        var orcidAuthenticate = function (intent, orcidAlreadyExists) {
            // send the user to orcid.org to authenticate
            // orcid will send them back to us from there.
            // @intent should be either "register" or "login".
            // @orcidAlreadyExists (bool) lets us know whether to send you to
            //      the ORCID login screen or signup screen.

            var redirectUri = window.location.origin + "/oauth/" + intent + "/orcid"

            console.log("ORCID authenticate!", showLogin)

            var authUrl = "https://orcid.org/oauth/authorize" +
                "?client_id=APP-PF0PDMP7P297AU8S" +
                "&response_type=code" +
                "&scope=/authenticate" +
                "&redirect_uri=" + redirectUri

            if (orcidAlreadyExists){
                authUrl += "&show_login=true"
            }

            window.location = authUrl
            return true
        }

        function getProfileUrl(){
            var data = getAllDataAsObject()

            console.log("getProfileUrl()", data)


            return false

            if (data.finished_wizard){
                return "u/" + data.orcid_id
            }

            if (data.num_products > 0){
                return "wizard/confirm-products"

            }

            if (data.orcid_id){
                return "wizard/add-publications"
            }

            return "wizard/connect-orcid"
        }





        function getAllDataAsObject(){
            if (!$auth.isAuthenticated){
                return {}
            }
            return $auth.getPayload()
        }

        function setFromToken(token){
            $auth.setToken(token) // synchronous
            sendTokenToIntercom()
        }

        return {
            isAuthenticatedPromise: isAuthenticatedPromise,
            twitterAuthenticate: twitterAuthenticate,
            orcidAuthenticate: orcidAuthenticate,
            setFromToken: setFromToken,
            getProfileUrl: getProfileUrl
        }
    })