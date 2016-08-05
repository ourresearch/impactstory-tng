console.log("loading")
angular.module('auth', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/oauth/:intent/:source', {
            templateUrl: "auth/oauth.tpl.html",
            controller: "OauthCtrl"
        })
    })


    .config(function ($routeProvider) {
        $routeProvider.when('/login', {
            templateUrl: "auth/login.tpl.html",
            controller: "LoginCtrl"
        })
    })


    .controller("LoginCtrl", function($scope, $location, $http, $auth){
        console.log("LoginCtrl is running!")
        $scope.loginTwitter = function(){
            console.log("login twitter")
        }
        $scope.loginOrcid = function(){
            console.log("login orcid")
        }

    })

    .controller("OauthCtrl", function($scope, $routeParams, $location, $http, CurrentUser){
        var requestObj = $location.search()
        if (_.isEmpty(requestObj)){
            console.log("we didn't get any codes or verifiers in the URL. aborting.")
            $location.url("/")
            return false
        }

        // todo i think we need to delete the twitter-register.tpl.html stuff in /wizard


        // REGISTERING WITH TWITTER
        if ($routeParams.intent=='register' && $routeParams.source=='twitter'){
            console.log("register with twitter")
            $http.post("api/auth/register/twitter", requestObj)
                .success(function(resp){
                    console.log("registered a new user with twitter", resp)
                    CurrentUser.load(resp.token)
                })
                .error(function(resp){
                  //console.log("problem getting token back from server!", resp)
                  //  $location.url("/")
                })
        }



        // CONNECTING ORCID
        if ($routeParams.intent=='connect' && $routeParams.source=='orcid'){
            console.log("connect orcid")
            requestObj.redirectUri = $rootScope.orcidRedirectUri
            $http.post("api/me/orcid", requestObj)
                .success(function(resp){
                    console.log("we successfully added an ORCID!", resp)
                    CurrentUser.load(resp.token)
                })
                .error(function(resp){
                  console.log("problem getting token back from server!", resp)
                    //$location.url("/")
                })
        }



        // LOGGING IN WITH TWITTER
        if ($routeParams.intent=='login' && $routeParams.source=='twitter'){
            console.log("log in with twitter")

        }



        // LOGGING IN WITH ORCID
        if ($routeParams.intent=='login' && $routeParams.source=='orcid'){
            console.log("log in with orcid")
        }

    })










