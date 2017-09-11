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
        $scope.filteredBadges = Group.badgesToShow(persons.grouped_badges)

        console.log("$scope.filteredBadges", $scope.filteredBadges)

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

        // posts and timeline stuff
        var posts = []
        _.each(persons.product_list, function(product){
            var myDoi = product.doi
            var myPublicationId = product.id
            var myTitle = product.title
            _.each(product.posts, function(myPost){
                myPost.citesDoi = myDoi
                myPost.citesPublication = myPublicationId
                myPost.citesTitle = myTitle
                posts.push(myPost)
            })
        })

        function makePostsWithRollups(posts){
            var sortedPosts = _.sortBy(posts, "posted_on")
            var postsWithRollups = []
            function makeRollupPost(){
                return {
                    source: 'tweetRollup',
                    posted_on: '',
                    count: 0,
                    tweets: []
                }
            }
            var currentRollup = makeRollupPost()
            _.each(sortedPosts, function(post){
                if (post.source == 'twitter'){ // this post is a tween

                    // we keep tweets as regular posts too
                    postsWithRollups.push(post)

                    // put the tweet in the rollup
                    currentRollup.tweets.push(post)

                    // rollup posted_on date will be date of *first* tweet in group
                    currentRollup.posted_on = post.posted_on
                }
                else {
                    postsWithRollups.push(post)

                    // save the current rollup
                    if (currentRollup.tweets.length){
                        postsWithRollups.push(currentRollup)
                    }

                    // clear the current rollup
                    currentRollup = makeRollupPost()
                }
            })

            // there may be rollup still sitting around because no regular post at end
            if (currentRollup.tweets.length){
                postsWithRollups.push(currentRollup)
            }
            return postsWithRollups
        }

        $scope.posts = makePostsWithRollups(posts)

        $scope.postsFilter = function(post){
            if ($scope.selectedChannel) {
                return post.source == $scope.selectedChannel.source_name
            }
            else { // we are trying to show unfiltered view

                // but even in unfiltered view we want to hide tweets.
                return post.source != 'twitter'

            }
        }

        $scope.postsSum = 0
        _.each(persons.source_list, function(v){
            $scope.postsSum += v.posts_count
        })

        $scope.selectedChannel = _.findWhere(persons.source_list, {source_name: $routeParams.filter})

        $scope.toggleSelectedChannel = function(channel){
            console.log("toggling selected channel", channel)
            if (channel.source_name == $routeParams.filter){
                $location.url("g/" + $scope.title +  "/timeline" + $scope.url_params)
            }
            else {
                $location.url("g/" + $scope.title + "/timeline/" + channel.source_name + $scope.url_params)
            }
        }


    })