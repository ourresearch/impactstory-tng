angular.module('auth', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/orcid-login', {
            templateUrl: "auth/orcid-login.tpl.html",
            controller: "OrcidLoginCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/twitter-login', {
            templateUrl: "auth/twitter-login.tpl.html",
            controller: "TwitterLoginCtrl"
        })
    })

    .controller("TwitterLoginCtrl", function($scope, $location, $http, $auth){
        console.log("twitter page controller is running!")

        var searchObject = $location.search();
        var token = searchObject.oauth_token
        var verifier = searchObject.oauth_verifier

        if (!token || !verifier){
            console.log("twitter didn't give oauth_verifier and a oauth_token")
            $location.url("/")
            return false
        }

        var requestObj = {
            token: token,
            verifier: verifier
        }

        $http.post("api/auth/twitter/register", requestObj)
            .success(function(resp){
                console.log("logged in a twitter user", resp)
                $auth.setToken(resp.token)
                $location.url("wizard/welcome")
                //var payload = $auth.getPayload()
                //
                //$rootScope.sendCurrentUserToIntercom()
                //$location.url("u/" + payload.sub)
            })
            .error(function(resp){
              //console.log("problem getting token back from server!", resp)
              //  $location.url("/")
            })



    })


    .controller("OrcidLoginCtrl", function ($scope, $location, $http, $auth, $rootScope, Person) {
        console.log("ORCID login page controller is running!")


        var searchObject = $location.search();
        var code = searchObject.code
        if (!code){
            $location.path("/")
            return false
        }

        var requestObj = {
            code: code,
            redirectUri: $rootScope.orcidRedirectUri
        }
        console.log("POSTing the request code to the server", requestObj)

        // set an orcid for the current user
        if ($auth.isAuthenticated()){
            $http.post("api/me/orcid_id", requestObj)
                .success(function(resp){
                    console.log("we successfully added an ORCID!", resp)
                    $auth.setToken(resp.token)
                    if ($auth.getPayload().num_products > 0) {
                        console.log("they have some works, good! redirect to your-publications")
                        $location.url("wizard/my-publications")
                    }
                    else {
                        console.log("they have no works. redirect to page to add-publications")
                        $location.url("wizard/add-publications")

                    }

                    //$rootScope.sendCurrentUserToIntercom()
                    //$location.url("u/" + payload.sub)
                })
                .error(function(resp){
                  console.log("problem getting token back from server!", resp)
                    //$location.url("/")
                })


        }

        // log a user in based on their ownership of this orcid
        else {

        }



        //$http.post("api/auth/orcid", requestObj)
        //    .success(function(resp){
        //        console.log("got a token back from ye server", resp)
        //        $auth.setToken(resp.token)
        //        var payload = $auth.getPayload()
        //
        //        $rootScope.sendCurrentUserToIntercom()
        //        $location.url("u/" + payload.sub)
        //    })
        //    .error(function(resp){
        //      console.log("problem getting token back from server!", resp)
        //        $location.url("/")
        //    })

    })







