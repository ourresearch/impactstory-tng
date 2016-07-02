angular.module('wizard', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/wizard/welcome', {
            templateUrl: "wizard/welcome.tpl.html",
            controller: "LinkYourOrcidPageCtrl",
            resolve: {
                isLoggedIn: function($rootScope){
                    return $rootScope.isAuthenticatedPromise()
                }
            }
        })
    })



    .controller("LinkYourOrcidPageCtrl", function($scope, $location, $http, $auth){
        console.log("LinkYourOrcidPageCtrl is running!")


        $scope.hasOrcid = null
        $scope.doYouHaveAnOrcid = function(answer){
            console.log("setting doYouHaveAnOrcid", answer)
            $scope.hasOrcid = answer
            if (answer == 'yes'){

            }
            else if (answer == 'no'){

            }
            else if (answer == 'maybe'){

            }
        }


    })










