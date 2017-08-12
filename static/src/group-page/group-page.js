angular.module('groupPage', [
    'ngRoute',
    'group'
])
    .config(function($routeProvider) {
        $routeProvider.when('/g/:group_name/', {
            templateUrl: 'group-page/group-page.tpl.html',
            controller: 'groupPageCtrl',
            reloadOnSearch: false,
            resolve: {
                persons: function($route, Group){
                    return Group.getPersons($route.current.params.persons)
                }
            }
        })
    })

    .controller("groupPageCtrl", function($scope, $route, persons) {
      $scope.logo_url = $route.current.params.logo_url
      $scope.title = $route.current.params.group_name
      debugger;
      $scope.persons = persons

    })