from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from models.country import country_info
from models.scientist_stars import scientists_twitter

from app import db
from util import date_as_iso_utc
from util import conversational_number
from util import calculate_percentile
from util import days_ago
from util import as_proportion

import datetime
import shortuuid
from textstat.textstat import textstat


def get_badge_assigner(name):
    for assigner in all_badge_assigners():
        if assigner.__name__ == name:
            return assigner
    return dummy_badge_assigner

def all_badge_assigner_names():
    return [assigner().name for assigner in all_badge_assigners()]

def all_badge_assigners():
    assigners = BadgeAssigner.__subclasses__()
    assigners.sort(key=lambda x: x.group)
    return assigners

def badge_configs():
    configs = {}
    for assigner in all_badge_assigners():
        if assigner.show_in_ui and assigner.valid_badge:
            configs[assigner.__name__] = assigner.config_dict()
    return configs


class Badge(db.Model):
    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))
    created = db.Column(db.DateTime)
    value = db.Column(db.Float)
    percentile = db.Column(db.Float)
    support = db.Column(db.Text)
    products = db.Column(MutableDict.as_mutable(JSONB))


    def __init__(self, assigned=True, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        self.assigned = assigned
        self.products = {}
        super(Badge, self).__init__(**kwargs)

    @property
    def dois(self):
        if self.products:
            return self.products.keys()
        return []

    @property
    def num_products(self):
        if self.products:
            return len(self.products)
        else:
            return 0

    def add_product(self, my_product):
        self.products[my_product.doi] = True

    def add_products(self, products_list):
        for my_product in products_list:
            self.add_product(my_product)

    def remove_all_products(self):
        self.products = {}

    @property
    def my_badge_type(self):
        assigner = get_badge_assigner(self.name)
        if assigner:
            my_assigner = assigner()
        else:
            my_assigner = dummy_badge_assigner()
        return my_assigner

    @property
    def sort_score(self):

        if self.percentile:
            sort_score = self.percentile * self.my_badge_type.importance
        else:
            sort_score = 0.5 * self.my_badge_type.importance

        if self.my_badge_type.group == "fun":
            sort_score -= 0.25
        return sort_score

    @property
    def description(self):
        description_template = self.my_badge_type.description
        description_string = description_template.format(
            value=conversational_number(self.value),
            one_hundred_minus_value=conversational_number(100-self.value)
        )
        return description_string

    @property
    def display_in_the_top_percentile(self):
        if not self.percentile:
            return None
        ret = int(100 - self.percentile * 100)
        if ret == 100:
            ret = 99
        if ret < 1:
            ret = 1
        return ret

    @property
    def display_percentile(self):
        if not self.percentile:
            return None
        ret = int(self.percentile * 100)
        if ret == 100:
            ret = 99
        if ret < 1:
            ret = 1
        return ret

    # what the UI is currently expecting
    @property
    def display_percentile_fraction(self):
        if not self.percentile:
            return None

        if self.percentile > 0.99:
            return 0.99
        return self.percentile

    @property
    def context(self):
        context_template = self.my_badge_type.context
        if context_template == None:
            context_template = u"  This puts you in the top {in_the_top_percentile}% of researchers."

        inverse_percentiles = ["reading_level"]
        if self.name in inverse_percentiles:
            if u"{percentile}" in context_template:
                if self.display_percentile > 50:
                    return None
            if u"{in_the_top_percentile}" in context_template:
                if self.display_in_the_top_percentile < 50:
                    return None

        else:
            if u"{percentile}" in context_template:
                if self.display_percentile < 50:
                    return None
            if u"{in_the_top_percentile}" in context_template:
                if self.display_in_the_top_percentile > 50:
                    return None

        context_string = context_template.format(
            value=conversational_number(self.value),
            one_hundred_minus_value=conversational_number(100-self.value),
            in_the_top_percentile=self.display_in_the_top_percentile,
            percentile=self.display_percentile
        )

        return context_string

    @property
    def group(self):
        return self.my_badge_type.group


    @property
    def support_items(self):
        try:
            parts = self.support.split(": ")
        except AttributeError:
            return None

        try:
            support_phrase = parts[1]
        except IndexError:
            return None

        items = support_phrase.split(",")
        trimmed = [x.strip() for x in items]
        deduped = list(set(trimmed))
        deduped.sort()
        return deduped


    @property
    def support_intro(self):
        try:
            parts = self.support.split(": ")
        except AttributeError:
            return None

        return parts[0]



    def set_percentile(self, refset_list):
        if refset_list:
            self.percentile = calculate_percentile(refset_list, self.value)
            # print u"set percentile for {} {} to {}".format(self.name, self.value, self.percentile)
        else:
            print "not setting percentile, no refest.  maybe local?"


    def __repr__(self):
        return u'<Badge {id} {name} ({value})>'.format(
            id=self.id,
            name=self.name,
            value=self.value
        )

    def to_dict(self):
        if self.products:
            product_list = self.products.keys()

        resp =  {
            "id": self.id,
            "name": self.name,
            "created": date_as_iso_utc(self.created),
            "show_in_ui": self.my_badge_type.show_in_ui,
            "support_items": self.support_items,
            "support_intro": self.support_intro,
            "support_finale": self.my_badge_type.support_finale,
            "value": self.value,
            "importance": self.my_badge_type.importance,
            "percentile": self.display_percentile_fraction,
            "sort_score": self.sort_score,
            "description": self.description,
            "extra_description": self.my_badge_type.extra_description,
            "context": self.context,
            "group": self.my_badge_type.group,
            "display_name": self.my_badge_type.display_name
        }
        return resp


class BadgeAssigner(object):
    display_name = ""
    group = None
    description = ""
    extra_description = None
    img_url = None
    video_url = None
    credit = None
    value = None
    importance = 1
    context = None
    support_intro = None
    support_finale = None
    pad_percentiles_with_zeros = True
    valid_badge = True
    show_in_ui = True

    def __init__(self):
        self.candidate_badge = Badge(name=self.__class__.__name__)
        self.assigned = False

    @property
    def name(self):
        return self.__class__.__name__

    # override this in subclasses
    def decide_if_assigned(self, person):
        return None

    def get_badge_or_None(self, person):
        self.decide_if_assigned(person)
        if self.assigned:
            return self.candidate_badge
        return None

    @classmethod
    def config_dict(cls):
        resp = {
            "name": cls.__name__,
            "display_name": cls.display_name,
            "group": cls.group,
            "description": cls.description,
        }
        return resp



# for use when other things have been deleted
class dummy_badge_assigner(BadgeAssigner):
    valid_badge = False


class depsy(BadgeAssigner):
    display_name = "Software Reuse"
    group = "openness"
    description = u"Your research software keeps on giving.  Your software impact is in the top {value} percent of all research software creators on Depsy."
    importance = .6
    context = ""

    def decide_if_assigned(self, person):
        if person.depsy_id and person.depsy_percentile:
            self.assigned = True
            self.candidate_badge.value = person.depsy_percentile * 100
            # self.candidate_badge.support = u"You are in the {} percentile <a href='http://depsy.org/person/{}'>on Depsy</a>.".format(
            #     round(person.depsy_percentile * 100, 0),
            #     person.depsy_id
            # )


class reading_level(BadgeAssigner):
    display_name = "All Readers Welcome"
    group = "openness"
    description = u"Your writing has a reading level that is easily understood at grade {value} and above, based on its abstracts and titles."
    importance = .5
    context = u"That's great &mdash; it helps lay people and practitioners use your research.  " \
              u"It also puts you in the top {percentile}% in readability."
    pad_percentiles_with_zeros = False

    def decide_if_assigned(self, person):
        reading_levels = {}
        for my_product in person.all_products:
            text = ""
            if my_product.title:
                text += u" " + my_product.title
            if my_product.get_abstract_using_mendeley():
                text += u" " + my_product.get_abstract_using_mendeley()

            # only do if at least three words between periods,
            # otherwise textstat library prints too many Not Enough Words error messages
            if text:
                sentences = text.split(".")
                if any([len(sentence.split())>3 for sentence in sentences]):
                    try:
                        grade_level = textstat.flesch_kincaid_grade(text)
                        # print u"grade level is {} for {}; text: {}".format(grade_level, my_product.doi, text)
                        if grade_level > 0:
                            # is sometimes negative, strangely.  examples in ethan's profile
                            reading_levels[my_product.doi] = grade_level
                    except TypeError:  #if text is too short it thows this
                        pass

        if reading_levels.values():
            average_reading_level = sum(reading_levels.values()) / float(len(reading_levels))
            if average_reading_level <= 14:
                self.candidate_badge.value = average_reading_level
                self.assigned = True



class big_hit(BadgeAssigner):
    display_name = "Greatest Hit"
    group = "buzz"
    description = u"Your top publication has been saved and shared {value} times."
    importance = .5
    context = u"Only {in_the_top_percentile}% of researchers get this much attention on a publication."

    def decide_if_assigned(self, person):
        self.candidate_badge.value = 0
        for my_product in person.products:
            if my_product.num_mentions > self.candidate_badge.value:
                self.assigned = True
                self.candidate_badge.value = my_product.num_mentions
                self.candidate_badge.remove_all_products()
                self.candidate_badge.add_product(my_product)
                self.candidate_badge.support = u"Your greatest hit online is <a href='/u/{orcid_id}/p/{id}'>{title}</a>.".format(
                    id=my_product.id,
                    orcid_id=my_product.orcid_id,
                    title=my_product.title
                )


class wiki_hit(BadgeAssigner):
    display_name = "Wikitastic"
    group = "engagement"
    description = u"Your research is mentioned in {value} Wikipedia articles!"
    importance = .9
    context = u"Only {in_the_top_percentile}% of researchers are this highly cited in Wikipedia."

    def decide_if_assigned(self, person):
        num_wikipedia_posts = person.post_counts_by_source("wikipedia")
        if num_wikipedia_posts >= 1:
            self.assigned = True
            self.candidate_badge.value = num_wikipedia_posts

            urls = person.wikipedia_urls
            self.candidate_badge.add_products([p for p in person.products_with_dois if p.has_source("wikipedia")])
            self.candidate_badge.support = u"Your Wikipedia titles include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support


class global_reach(BadgeAssigner):
    display_name = "Global Reach"
    group = "engagement"
    description = u"Your research has been saved and shared in {value} countries."
    importance = .8
    support_finale = " countries."
    context = u"That's high: only {in_the_top_percentile}% of researchers get that much international attention."

    def decide_if_assigned(self, person):
        if len(person.countries_using_mendeley) > 1:
            self.assigned = True
            self.candidate_badge.value = len(person.countries_using_mendeley)
            self.candidate_badge.support = u"Countries include: {}".format(", ".join(person.countries_using_mendeley))


class megafan(BadgeAssigner):
    display_name = "Follower Frenzy"
    group = "engagement"
    description = u"Someone with {value} followers has tweeted your research."
    importance = .2
    context = u"Only {in_the_top_percentile}% of scholars have been tweeted by someone with this many followers."

    def decide_if_assigned(self, person):
        biggest_fan = None

        self.candidate_badge.value = 0
        for my_product in person.products_with_dois:
            for fan_name, followers in my_product.twitter_posters_with_followers.iteritems():
                if followers >= self.candidate_badge.value and followers > 1000:
                    self.assigned = True
                    self.candidate_badge.value = followers
                    self.candidate_badge.remove_all_products()  # clear them
                    self.candidate_badge.add_product(my_product)  # add the one for the new max
                    biggest_fan = fan_name

        self.candidate_badge.support = u"Thanks, <a href='http://twitter.com/{fan}'>@{fan}</a>.".format(
            fan=biggest_fan)


class hot_streak(BadgeAssigner):
    display_name = "Hot Streak"
    group = "buzz"
    description = u"People keep talking about your research. Someone has shared your research online every month for the last {value} months."
    importance = .5
    context = u"That's a sharing streak matched by only {in_the_top_percentile}% of scholars."

    def decide_if_assigned(self, person):
        streak = True
        streak_length = 0
        all_event_days_ago = [days_ago(e) for e in person.get_event_dates()]
        for month in range(0, 10*12):  # do up to 10 years
            streak_length += 1
            relevant_days = [month*30 + day for day in range(0, 30)]
            matching_days_count = len([d for d in all_event_days_ago if d in relevant_days])
            if matching_days_count <= 0:
                # print "broke the streak"
                break
        if streak_length > 1:
            self.assigned = True
            self.candidate_badge.value = streak_length


class clean_sweep(BadgeAssigner):
    display_name = "Clean Sweep"
    group = "buzz"
    description = "Every one of your publications since 2012 has been saved and shared online."
    importance = .1
    context = u"Fewer than a quarter of researchers show this kind of consistency."

    def decide_if_assigned(self, person):
        num_with_metrics = 0
        num_applicable = 0
        for my_product in person.products:
            if my_product.year > 2011:
                num_applicable += 1
                if my_product.has_mentions:
                    num_with_metrics += 1
                    self.candidate_badge.add_product(my_product)

        if (num_with_metrics >= num_applicable) and (num_with_metrics >= 2):
            self.assigned = True
            self.candidate_badge.value = 1


class global_south(BadgeAssigner):
    display_name = "Global South"
    group = "engagement"
    description = u"Of people who save and share your research, {value}% are in the Global South."
    importance = .4
    context = u"That's a high proportion: only {in_the_top_percentile}% of researchers publish work that inspires this level of engagement from the developing world."

    def decide_if_assigned(self, person):
        countries = set()

        total_geo_located_posts = 0.0
        total_global_south_posts = 0.0

        for my_product in person.all_products:
            for country_name, count in my_product.post_counts_by_country_using_mendeley.iteritems():
                total_geo_located_posts += count
                if country_name:
                    try:
                        if country_info[country_name]["is_global_south"]:
                            total_global_south_posts += count
                            self.candidate_badge.add_product(my_product)
                            countries.add(country_name)
                    except (KeyError, ):
                        print u"ERROR: Nothing in dict for country name {}".format(country_name)
                        # raise  # keep going for now

        if total_geo_located_posts >= 10:
            ratio = (total_global_south_posts / total_geo_located_posts)
            if ratio >= 0.1:
                self.assigned = True
                self.candidate_badge.value = round(100.0 * ratio, 2)
                self.candidate_badge.support = "Countries include: {}".format(
                    ", ".join(sorted(countries)))



def proportion_poster_counts_by_type(person, poster_type):
    total_posters_with_type = 0.0
    my_type = 0.0
    for my_product in person.products_with_dois:
        total_posters_with_type += sum(my_product.poster_counts_by_type.values())
        if poster_type in my_product.poster_counts_by_type:
            my_type += my_product.poster_counts_by_type[poster_type]

    if total_posters_with_type:
        return (my_type / total_posters_with_type)
    else:
        return 0


class open_science_triathlete(BadgeAssigner):
    display_name = "Open Science Triathlete"
    group = "openness"
    description = u"Congratulations, you hit the trifecta. You have an Open Access paper, open dataset, and open source software."
    importance = .5

    def decide_if_assigned(self, person):
        has_oa_paper = [p.doi for p in person.products if p.has_fulltext_url and p.guess_genre() == "article"]
        has_data = [p.id for p in person.all_products if p.guess_genre()=="dataset"]
        if person.depsy_id:
            has_software = True
        else:
            has_software = [p.id for p in person.all_products if p.guess_genre()=="software"]

        if (has_oa_paper and has_data and has_software):
            self.assigned = True
            self.candidate_badge.value = 1


class all_fulltext(BadgeAssigner):
    display_name = "OA Hero"
    group = "openness"
    description = u"100% of your research is free to read online."
    context = u"This level of availability puts you in the top {in_the_top_percentile}% of researchers."
    importance = .99
    show_in_ui = False

    def decide_if_assigned(self, person):
        if person.num_products >= 3 and person.percent_fulltext:
            if person.percent_fulltext >= 1.0:
                self.candidate_badge.value = person.percent_fulltext * 100
                self.assigned = True


class percent_fulltext(BadgeAssigner):
    display_name = "Open Access"
    group = "openness"
    description = u"{value}% of your research is free to read online."
    context = u"This level of availability puts you in the top {in_the_top_percentile}% of researchers."
    importance = .9

    def decide_if_assigned(self, person):
        if person.num_products >= 3 and person.percent_fulltext:
            if person.percent_fulltext >= 0.5:
                self.candidate_badge.value = person.percent_fulltext * 100
                self.assigned = True
                if person.percent_open_license > 0:
                    self.candidate_badge.support = \
                        u'Even better, {}% of your papers are published under a fully Open license like CC-BY, making them available for a wide range of reuse (not just reading). Learn more about why this is important at <a href="http://sparcopen.org/our-work/howopenisit/">HowOpenIsIt.</a>'.format(
                            int(person.percent_open_license * 100))
                else:
                    self.candidate_badge.support = ""



class open_license(BadgeAssigner):
    display_name = "Open License"
    group = "openness"
    description = u"{value}% of your research has a CC-BY, CC0, or public domain license."
    context = u"This level of availability puts you in the top {in_the_top_percentile}% of researchers."
    importance = .8
    show_in_ui = False

    def decide_if_assigned(self, person):
        if person.num_products >= 3 and person.percent_open_license:
            if person.percent_open_license >= 0.1:
                self.candidate_badge.value = person.percent_open_license * 100
                self.assigned = True



class rick_roll(BadgeAssigner):
    display_name = "Rickroll"
    group = "fun"
    description = u"""You have been tweeted by a person named Richard!
                  A recent study found this is correlated with a 19% boost in citations <a href='https://www.youtube.com/watch?v=dQw4w9WgXcQ'>[source]</a>."""
    importance = 0.35
    context = u"Only {in_the_top_percentile}% of researchers get this achievement."


    def decide_if_assigned(self, person):
        for my_product in person.products_with_dois:
            for name in my_product.get_tweeter_posters_full_names():
                match = False
                if name.lower().endswith("richard"):
                    match = True
                else:
                    for name_part in name.lower().split(" ")[:-1]:  # don't include last name
                        if name_part in ["rick", "rich", "ricky", "dick", "richard"]:
                            match = True
                if match:
                    self.assigned = True
                    self.candidate_badge.value = 1
                    self.candidate_badge.add_product(my_product)
                    # self.candidate_badge.support = u"Thanks, {}".format(name)

        # if self.assigned:
        #     print "RICK!!!!", self.candidate_badge.support


class big_in_japan(BadgeAssigner):
    display_name = "Big in Japan"
    group = "fun"
    description = u"Your work was saved or shared by someone in Japan!"
    video_url = "https://www.youtube.com/watch?v=tl6u2NASUzU"
    credit = 'Alphaville - "Big In Japan"'
    importance = 0.3
    context = u"Only half of researchers <a href='https://www.youtube.com/watch?v=tl6u2NASUzU'>can claim this honor.</a>"

    def decide_if_assigned(self, person):
        for my_product in person.all_products:
            if my_product.has_country_using_mendeley("Japan"):
                self.candidate_badge.add_product(my_product)
                self.assigned = True
                self.candidate_badge.value = 1



class famous_follower(BadgeAssigner):
    display_name = "Kind of a Big Deal"
    group = "fun"
    description = u"""Cool! Your research has been tweeted by {value}
                  scientists who are considered Big Deals on Twitter <a href='http://www.sciencemag.org/news/2014/09/top-50-science-stars-twitter'>[source]</a>."""
    importance = 0.3
    context = u"This isn't common: only {in_the_top_percentile}% of other researchers have been mentioned by these twitter stars."

    def decide_if_assigned(self, person):
        fans = set()
        for my_product in person.products_with_dois:
            for twitter_handle in my_product.twitter_posters_with_followers:
                try:
                    if twitter_handle.lower() in scientists_twitter:
                        fans.add(twitter_handle)
                        self.candidate_badge.add_product(my_product)
                except AttributeError:
                    pass

        if len(fans) > 1:
            self.assigned = True
            self.candidate_badge.value = len(fans)
            fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
            self.candidate_badge.support = u"The Big Deal Scientists who tweeted your research include: {}".format(u",".join(fan_urls))




# class librarian(BadgeAssigner):
#     display_name = "Librarian Love"
#     group = "engagement"
#     description = u"Librarians love you: {value}% of your bookmarks come from librarians."
#     importance = 0.3
#     context = u"Only {in_the_top_percentile}% of other researchers get this much librarian attention."
#     show_in_ui = False
#
#     def decide_if_assigned(self, person):
#         try:
#             librarian_percent = as_proportion(person.mendeley_job_titles)["Librarian"]
#             if librarian_percent >= 0.15:
#                 self.assigned = True
#                 self.candidate_badge.value = librarian_percent * 100
#         except KeyError:
#             pass

# class faculty(BadgeAssigner):
#     display_name = "Faculty Fav"
#     group = "engagement"
#     description = u"You are a faculty favorite: {value}% of your bookmarks come from faculty."
#     importance = 0.3
#     context = u"Only {in_the_top_percentile}% of other researchers get this much faculty attention."
#     show_in_ui = False
#
#     def decide_if_assigned(self, person):
#         try:
#             faculty_percent = as_proportion(person.mendeley_job_titles)["Faculty"]
#             if faculty_percent >= 0.15:
#                 self.assigned = True
#                 self.candidate_badge.value = faculty_percent * 100
#         except KeyError:
#             pass

# class teaching(BadgeAssigner):
#     display_name = "Teaching Goodness"
#     group = "engagement"
#     description = u"Your research helps newbies get started: {value}% of your bookmarks come from undergrad and Master's students."
#     importance = 0.4
#     context = u"This level of student interest puts you in the top {in_the_top_percentile}% of researchers."
#     show_in_ui = False
#
#     def decide_if_assigned(self, person):
#         student_percent = 0
#         if person.mendeley_job_titles and "Undergrad Student" in person.mendeley_job_titles:
#             student_percent += as_proportion(person.mendeley_job_titles)["Undergrad Student"]
#         if person.mendeley_job_titles and "Masters Student" in person.mendeley_job_titles:
#             student_percent += as_proportion(person.mendeley_job_titles)["Masters Student"]
#
#         if student_percent >= 0.33 and person.mendeley_readers >= 3:
#             self.assigned = True
#             self.candidate_badge.value = student_percent * 100

# class teaching_phd(BadgeAssigner):
#     display_name = "Teaching Goodness"
#     group = "engagement"
#     description = u"Your research helps newbies get started: {value}% of your bookmarks come from undergrad and graduate students."
#     importance = 0.4
#     context = u"This level of student interest puts you in the top {in_the_top_percentile}% of researchers."
#     show_in_ui = False
#
#     def decide_if_assigned(self, person):
#         student_percent = 0
#         if person.mendeley_job_titles and "Undergrad Student" in person.mendeley_job_titles:
#             student_percent += as_proportion(person.mendeley_job_titles)["Undergrad Student"]
#         if person.mendeley_job_titles and "Masters Student" in person.mendeley_job_titles:
#             student_percent += as_proportion(person.mendeley_job_titles)["Masters Student"]
#         if person.mendeley_job_titles and "PhD Student" in person.mendeley_job_titles:
#             student_percent += as_proportion(person.mendeley_job_titles)["PhD Student"]
#
#         if student_percent >= 0.33 and person.mendeley_readers >= 3:
#             self.assigned = True
#             self.candidate_badge.value = student_percent * 100


# class interdisciplinarity(BadgeAssigner):
#     display_name = "Interdisciplinary Delight"
#     group = "engagement"
#     description = u"Your research is cross-over hit: people in {value} different fields have heavily bookmarked your papers."
#     importance = 0.8
#     context = u"Only {in_the_top_percentile}% of researchers receive as much attention in as many disciplines."
#     show_in_ui = False
#
#     def decide_if_assigned(self, person):
#         if not person.mendeley_disciplines:
#             return
#
#         discipline_proportions = as_proportion(person.mendeley_disciplines)
#         disciplines_above_threshold = []
#         for name, proportion in discipline_proportions.iteritems():
#             if proportion >= 0.1 and person.mendeley_disciplines[name] >= 5:
#                 disciplines_above_threshold.append(name)
#
#         if len(disciplines_above_threshold) >= 3:
#             self.assigned = True
#             self.candidate_badge.value = len(disciplines_above_threshold)
#             self.candidate_badge.support = u"The fields include: {}".format(
#                 ", ".join(sorted(disciplines_above_threshold)))




# class bff(BadgeAssigner):
#     display_name = "BFF"
#     group = "fun"
#     description = u"You have {value} <a href='https://en.wikipedia.org/wiki/Best_friends_forever'>BFFs</a>! {value} people have tweeted three or more of your papers."
#     importance = .4
#     context = ""
#     show_in_ui = False
#
#     def decide_if_assigned(self, person):
#         fan_counts = defaultdict(int)
#         fans = set()
#
#         for my_product in person.products_with_dois:
#             for fan_name in my_product.twitter_posters_with_followers:
#                 fan_counts[fan_name] += 1
#
#         for fan_name, tweeted_papers_count in fan_counts.iteritems():
#             if tweeted_papers_count >= 3:
#                 self.assigned = True
#                 fans.add(fan_name)
#
#         if self.assigned:
#             self.candidate_badge.value = len(fans)
#             fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
#             self.candidate_badge.support = u"BFFs include: {}".format(u",".join(fan_urls))
#


# inspired by https://github.com/ThinkUpLLC/ThinkUp/blob/db6fbdbcc133a4816da8e7cc622fd6f1ce534672/webapp/plugins/insightsgenerator/insights/followcountvisualizer.php
# class impressions(BadgeAssigner):
#     display_name = "Mass Exposure"
#     group = "engagement"
#     description = u"Your research has appeared Twitter timelines {value} times."
#     importance = .8
#     img_url = "https://en.wikipedia.org/wiki/File:Avery_fisher_hall.jpg"
#     credit = "Photo: Mikhail Klassen"
#     context = u"That's a lot of impressions! Only {in_the_top_percentile}% of scholars have such a large Twitter audience."
#
#     def decide_if_assigned(self, person):
#         if person.impressions > 1000:
#             self.assigned = True
#             self.candidate_badge.value = person.impressions


# class babel(BadgeAssigner):
#     display_name = "Multilingual"
#     group = "engagement"
#     description = u"People talk about your research in English &mdash; and {value} other languages!"
#     # extra_description = "Due to issues with the Twitter API, we don't have language information for tweets yet."
#     importance = .85
#     context = u"Only {in_the_top_percentile}% of researchers have their work discussed in this many languages."
#
#     def decide_if_assigned(self, person):
#         languages_with_examples = {}
#
#         for my_product in person.products_with_dois:
#             languages_with_examples.update(my_product.languages_with_examples)
#             if len(set(my_product.languages_with_examples.keys()) - set(["en"])) > 0:
#                 self.candidate_badge.add_product(my_product)
#
#         if len(languages_with_examples) >= 1:
#             self.assigned = True
#             self.candidate_badge.value = len(languages_with_examples)
#             language_url_list = [u"<a href='{}'>{}</a>".format(url, lang)
#                  for (lang, url) in languages_with_examples.iteritems()]
#             self.candidate_badge.support = u"Your langauges include: {}".format(u", ".join(language_url_list))
#             # print self.candidate_badge.support



# class gender_balance(BadgeAssigner):
#     display_name = "Gender Balance"
#     group = "engagement"
#     description = u"Of the people who tweet about your research, {value}% are women and {one_hundred_minus_value}% are men."
#     importance = .5
#     # context = u"The average gender balance in our database is 30% women, 70% men."
#     context = u"That's a better balance than average &mdash; " \
#               u"only {in_the_top_percentile}% of researchers in our database are tweeted by this high a proportion of women."
#     pad_percentiles_with_zeros = False
#
#     # get the average gender balance using this sql
#     # select avg(value) from badge, person
#     # where badge.orcid_id = person.orcid_id
#     # and person.campaign='2015_with_urls'
#     # and name='gender_balance'
#
#
#     def decide_if_assigned(self, person):
#         self.candidate_badge.value = 0
#         tweeter_names = person.get_tweeter_names(most_recent=100)
#
#         counts = defaultdict(int)
#         detector = GenderDetector('us')
#
#         for name in tweeter_names:
#             first_name = HumanName(name)["first"]
#             if first_name:
#                 try:
#                     # print u"{} guessed as {}".format(first_name, detector.guess(first_name))
#                     counts[detector.guess(first_name)] += 1
#                 except KeyError:  # the detector throws this for some badly formed first names
#                     pass
#
#         if counts["male"] > 1:
#             ratio_female = counts["female"] / float(counts["male"] + counts["female"])
#             if ratio_female > 0.01:
#                 print u"counts female={}, counts male={}, ratio={}".format(
#                     counts["female"], counts["male"], ratio_female)
#                 self.candidate_badge.value = ratio_female * 100
#                 self.assigned = True
