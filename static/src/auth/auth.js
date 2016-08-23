console.log("loading")
angular.module('auth', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/oauth/:intent/:identityProvider', {
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

        requestObj.redirectUri = $location.path()
        CurrentUser.callMeEndpoint($routeParams.identityProvider, $routeParams.intent, requestObj)


    })










