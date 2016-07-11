angular.module('app', [

    // external libs
    'ngRoute',
    'ngMessages',
    'satellizer',

    'ngResource',
    'ngSanitize',
    'ngMaterial',

    // this is how it accesses the cached templates in ti.js
    'templates.app',

    // services
    'currentUser',
    'badgeDefs',
    'numFormat',
    'person',

    // pages
    'staticPages',
    'productPage', // MUST be above personPage because personPage route is greedy for /p/
    'personPage',
    'settingsPage',
    'badgePage',
    'aboutPages'


]);




angular.module('app').config(function ($routeProvider,
                                       $authProvider,
                                       $mdThemingProvider,
                                       $locationProvider) {


    $locationProvider.html5Mode(true);

    // handle 404s by redirecting to landing page.
    $routeProvider.otherwise({ redirectTo: '/' })

    $mdThemingProvider.theme('default')
        .primaryPalette('deep-orange')
        .accentPalette("blue")






    //$authProvider.twitter({
    //  url: '/auth/twitter',
    //  authorizationEndpoint: 'https://api.twitter.com/oauth/authenticate',
    //  redirectUri: window.location.origin + "/twitter-login",
    //  type: '1.0',
    //  popupOptions: { width: 495, height: 645 }
    //});



});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $q,
                                   $timeout,
                                   $auth,
                                   $http,
                                   $location,
                                   Person) {


    (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
            (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
        m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
    })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

    ga('create', 'UA-23384030-1', 'auto');

    // if the user is logged in, get the most up-to-date token
    if ($auth.isAuthenticated()){
        $http.get("api/me").success(function(resp){
            console.log("refreshing the current user's token", $auth.getPayload())
            $auth.setToken(resp.token)
        })
    }




    $rootScope.$on('$routeChangeStart', function(next, current){
    })
    $rootScope.$on('$routeChangeSuccess', function(next, current){
        window.scrollTo(0, 0)
        ga('send', 'pageview', { page: $location.url() });
        window.Intercom('update')

    })

    $rootScope.isAuthenticatedPromise = function(){
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

    $rootScope.sendCurrentUserToIntercom = function(){
        if (!$auth.isAuthenticated()){
            return false
        }

        $http.get("api/person/" + $auth.getPayload().sub)
            .success(function(resp){
                $rootScope.sendToIntercom(resp)
                console.log("sending current user to intercom")
            })
    }

    $rootScope.sendToIntercom = function(personResp){
        var resp = personResp
        var percentOA = resp.percent_fulltext
        if (percentOA === null) {
            percentOA = undefined
        }
        else {
            percentOA * 100
        }

        var intercomInfo = {
            // basic user metadata
            app_id: "z93rnxrs",
            name: resp._full_name,
            user_id: resp.orcid_id, // orcid ID
            claimed_at: moment(resp.claimed_at).unix(),
            email: resp.email,

            // user stuff for analytics
            percent_oa: percentOA,
            num_posts: resp.num_posts,
            num_mentions: resp.num_mentions,
            num_products: resp.products.length,
            num_badges: resp.badges.length,
            num_twitter_followers: resp.num_twitter_followers,
            campaign: resp.campaign,
            fresh_orcid: resp.fresh_orcid,

            // we don't send person responses for deleted users (just 404s).
            // so if we have a person response, this user isn't deleted.
            // useful for when users deleted profile, then re-created later.
            is_deleted: false

        }
        console.log("sending to intercom", intercomInfo)
        window.Intercom("boot", intercomInfo)
    }

    //$rootScope.sendCurrentUserToIntercom()
    








    $rootScope.$on('$routeChangeError', function(event, current, previous, rejection){
        console.log("$routeChangeError, redirecting to /")
        $rootScope.setPersonIsLoading(false)
        $location.url("/")
        window.scrollTo(0, 0)
    });




});





angular.module('app').controller('AppCtrl', function(
    $rootScope,
    $scope,
    $route,
    $location,
    NumFormat,
    $auth,
    $interval,
    $http,
    $mdDialog,
    $sce){

    $scope.auth = $auth
    $scope.numFormat = NumFormat
    $scope.moment = moment // this will break unless moment.js loads over network...

    $scope.global = {}
    $rootScope.setPersonIsLoading = function(isLoading){
        $scope.global.personIsLoading = !!isLoading
    }


    $scope.pageTitle = function(){
        if (!$scope.global.title){
            $scope.global.title = "Discover the online impact of your research"
        }
        return "Impactstory: " + $scope.global.title
    }


    $rootScope.$on('$routeChangeSuccess', function(next, current){
        $scope.global.showBottomStuff = true
        $scope.global.loggingIn = false
        $scope.global.title = null
        $scope.global.isLandingPage = false
        $location.search("source", null)
    })

    $scope.trustHtml = function(str){
        return $sce.trustAsHtml(str)
    }
    $scope.pluralize = function(noun, number){
        //pluralize.addSingularRule(/slides$/i, 'slide deck')
        return pluralize(noun, number)
    }



    // config stuff
    // badge group configs
    var badgeGroupIcons = {
        engagement: "user",
        openness: "unlock-alt",
        buzz: "bullhorn",
        fun: "smile-o"
    }
    $scope.getBadgeIcon = function(group){
        if (badgeGroupIcons[group]){
            return badgeGroupIcons[group]
        }
        else {
            return "fa-trophy"
        }
    }

    // genre config
    var genreIcons = {
        'article': "file-text-o",
        'blog': "comments",
        'dataset': "table",
        'figure': "bar-chart",
        'image': "picture-o",
        'poster': "map-o",
        'conference-poster': "map-o",
        'slides': "desktop",
        'software': "save",
        'twitter': "twitter",
        'video': "facetime-video",
        'webpage': "laptop",
        'online-resource': "desktop",
        'preprint': "paper-plane-o",
        'other': "ellipsis-h",
        'unknown': "file-o",
        "conference-paper": "list-alt",  // conference proceeding
        "book": "book",
        "book-chapter": "bookmark-o",  // chapter anthology
        "thesis": "graduation-cap",
        "dissertation": "graduation-cap",
        "peer-review": "comments-o"
    }
    $scope.getGenreIcon = function(genre){
        if (genreIcons[genre]){
            return genreIcons[genre]
        }
        else {
            return genreIcons.unknown
        }
    }


    $rootScope.twitterRedirectUri = {
        register: window.location.origin + "/twitter-register",
        login: window.location.origin + "/twitter-login"
    }

    // TWITTER AUTH
    var twitterAuthenticate = function (registerOrLogin) {
        console.log("authenticate with twitters!");

        // first get the OAuth token that we use to create the twitter URL
        // we will redirect the user too.
        var redirectUri = $rootScope.twitterRedirectUri[registerOrLogin]
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
    $rootScope.twitterAuthenticate = twitterAuthenticate
    $scope.twitterAuthenticate = twitterAuthenticate





    // ORCID AUTH

    $rootScope.orcidRedirectUri = {
        connect: window.location.origin + "/orcid-connect",
        login: window.location.origin + "/orcid-login"
    }

    // used in the nav bar, also for signup on the landing page.
    var orcidAuthenticate = function (showLogin, connectOrLogin) {
        console.log("ORCID authenticate!", showLogin)


        var authUrl = "https://orcid.org/oauth/authorize" +
            "?client_id=APP-PF0PDMP7P297AU8S" +
            "&response_type=code" +
            "&scope=/authenticate" +
            "&redirect_uri=" + $rootScope.orcidRedirectUri[connectOrLogin]

        if (showLogin == "register"){
            // will show the signup screen
        }
        else if (showLogin == "login") {
            // show the login screen (defaults to this)
            authUrl += "&show_login=true"
        }

        window.location = authUrl
        return true
    }
    $rootScope.orcidAuthenticate = orcidAuthenticate
    $scope.orcidAuthenticate = orcidAuthenticate



    var showAlert = function(msgText, titleText, okText){
        if (!okText){
            okText = "ok"
        }
          $mdDialog.show(
                  $mdDialog.alert()
                    .clickOutsideToClose(true)
                    .title(titleText)
                    .textContent(msgText)
                    .ok(okText)
            );
    }
    $rootScope.showAlert = showAlert









    /********************************************************
     *
     *  stripe stuff
     *
    ********************************************************/



    var stripeInfo = {
        email: null,
        tokenId: null,
        cents: 0,

        // optional
        fullName: null,
        orcidId: null
    }

    var stripeHandler = StripeCheckout.configure({
        key: stripePublishableKey,
        locale: 'auto',
        token: function(token) {
            stripeInfo.email = token.email
            stripeInfo.tokenId = token.id

            console.log("now we are doing things with the user's info", stripeInfo)
            $http.post("/api/donation", stripeInfo)
                .success(function(resp){
                    console.log("the credit card charge worked!", resp)
                    showAlert(
                        "We appreciate your donation, and we've emailed you a receipt.",
                        "Thanks so much!"
                    )
                })
                .error(function(resp){
                    console.log("error!", resp.message)
                    if (resp.message){
                        var reason = resp.message
                    }
                    else {
                        var reason = "Sorry, we had a server error! Drop us a line at team@impactstory.org and we'll fix it."
                    }
                    showAlert(reason, "Credit card error")
                })
        }
      });
    $scope.donate = function(cents){
        console.log("donate", cents)
        stripeInfo.cents = cents
        var me = $auth.getPayload() // this might break on the donate page.
        if (me){
            stripeInfo.fullName = me.given_names + " " + me.family_name
            stripeInfo.orcidId = me.sub
        }

        stripeHandler.open({
          name: 'Impactstory donation',
          description: "We're a US 501(c)3",
          amount: cents
        });
    }


})



.controller('badgeItemCtrl', function($scope){
    $scope.showMaxItems = 3
    $scope.getIconUrl = function(name){
    }
})

.controller('tweetRollupCtrl', function($scope){
    $scope.showTweets = false
})

.controller('mendeleyRollupCtrl', function($scope){
    $scope.showMendeley = false
})
    
.directive('subscorehelp', function(){
        return {
            restrict: "E",
            templateUrl: 'helps.tpl.html',
            scope:{
                subscoreName: "=name"
            },
            link: function(scope, elem, attrs){
            }
        }
    })

.directive('short', function(){
        return {
            restrict: "E",
            template: '{{shortText}}<span ng-show="shortened">&hellip;</span>',
            scope:{
                text: "=text",
                len: "=len"
            },
            link: function(scope, elem, attrs){

                var newLen
                if (scope.len) {
                    newLen = scope.len
                }
                else {
                    newLen = 40
                }
                if (scope.text.length > newLen){
                    var short = scope.text.substring(0, newLen)
                    short = short.split(" ").slice(0, -1).join(" ")
                    scope.shortText = short
                    scope.shortened = true
                }
                else {
                    scope.shortText = scope.text
                }

            }
        }
    })














