angular.module('groupPage', [
    'ngRoute',
    'group'
])
    .config(function($routeProvider) {
        $routeProvider.when('/g/:group_name/:tab?/:filter?/', {
            templateUrl: 'group-page/group-page.tpl.html',
            controller: 'groupPageCtrl',
            reloadOnSearch: false,
            resolve: {
                persons: function($route, Group){
                    return Group.getPersons($route.current.params.persons, $route.current.params.achievements)
                }
            }
        })
    })

    .controller("groupPageCtrl", function($scope, $route, $routeParams, $location, Group, persons) {
        $scope.logo_url = $route.current.params.logo_url
        $scope.title = $route.current.params.group_name
        $scope.persons = persons
        $scope.url_params = window.location.search
        $scope.badges = Group.badgesToShow(persons.badge_list)


        // genre stuff (don't know what it is)
        var genreGroups = _.groupBy(persons.product_list, "genre")
        var genres = []
        _.each(genreGroups, function(v, k){
            genres.push({
                name: k,
                display_name: k.split("-").join(" "),
                count: v.length
            })
        })

        $scope.genres = genres
        $scope.selectedGenre = _.findWhere(genres, {name: $routeParams.filter})
        $scope.toggleSeletedGenre = function(genre){
            if (genre.name === $routeParams.filter){
                $location.url("g/" + $scope.title + "/publications/" + $scope.url_params)
            }
            else {
                $location.url("g/" + $scope.title + "/publications/" + genre.name + '/' + $scope.url_params)
            }
        }

        $scope.tab =  $routeParams.tab || "top_investigators"
        $scope.viewItemsLimit = 20


        // some achievement stuff

        var badgeUrlName = function(badge){
           return badge.display_name.toLowerCase().replace(/\s/g, "-")
        }
        $scope.badgeUrlName = badgeUrlName

        $scope.shareBadge = function(badgeName){
            window.Intercom('trackEvent', 'tweeted-badge', {
                name: badgeName
            });
            var myOrcid = $auth.getPayload().sub // orcid ID
            window.Intercom("update", {
                user_id: myOrcid,
                latest_tweeted_badge: badgeName
            })
        }



    })