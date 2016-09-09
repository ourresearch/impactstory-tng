angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl",
            resolve: {
                sendToCorrectPage: function(CurrentUser){
                    return CurrentUser.sendToCorrectPage(false)
                },
                customLandingPage: function($q){
                    return $q.when("default")
                }
            }
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/opencon', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl",
            resolve: {
                sendToCorrectPage: function(CurrentUser){
                    return CurrentUser.sendToCorrectPage(false)
                },
                customLandingPage: function($q){
                    return $q.when("opencon")
                }
            }
        })
    })





    .config(function ($routeProvider) {
        $routeProvider.when('/page-not-found', {
            templateUrl: "static-pages/page-not-found.tpl.html",
            controller: "PageNotFoundCtrl"
        })
    })

    .controller("PageNotFoundCtrl", function($scope){
        console.log("PageNotFound controller is running!")

    })



    .controller("LandingPageCtrl", function ($scope,
                                             $mdDialog,
                                             $cookies,
                                             $rootScope,
                                             customLandingPage,
                                             $timeout) {

        if (customLandingPage == "opencon") {
            console.log("this is a custom landing page: ",customLandingPage)
            $scope.customPageName = "opencon"
            $cookies.put("sawOpenconLandingPage", true)

        }


        $scope.global.showBottomStuff = false;
        console.log("landing page!", $scope.global)
        $scope.global.isLandingPage = true

        var orcidModalCtrl = function($scope){
            console.log("IHaveNoOrcidCtrl ran" )
            $scope.modalAuth = function(){
                $mdDialog.hide()
            }
        }

        $scope.noOrcid = function(ev){
            $mdDialog.show({
                controller: orcidModalCtrl,
                templateUrl: 'orcid-dialog.tmpl.html',
                clickOutsideToClose:true,
                targetEvent: ev
            })
                .then(
                function(){
                    $rootScope.authenticate("signin")
                },
                function(){
                    console.log("they cancelled the dialog")
                }
            )


        }

    })
    .controller("IHaveNoOrcidCtrl", function($scope){
        console.log("IHaveNoOrcidCtrl ran" )
    })










