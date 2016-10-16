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
                redirect: function(CurrentUser){
                    return CurrentUser.sendHomePromise(false)
                }
            }
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/landing/:landingPageName', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl",
            resolve: {
                redirect: function(CurrentUser){
                    return CurrentUser.sendHomePromise(false)
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
                                             $routeParams,
                                             $timeout) {

        if ($routeParams.landingPageName) {
            console.log("this is a custom landing page: ", $routeParams.landingPageName)
            $scope.customPageName = $routeParams.landingPageName
            if ($routeParams.landingPageName == "open"){
                $cookies.put("sawOpenconLandingPage", true) // legacy
                $cookies.put("customLandingPage", $routeParams.landingPageName)
            }

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










