# MIT License
#
# Copyright (c) 2019 Creative Commons
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# from __future__ imports must occur at the beginning of the file. DO NOT CHANGE!
from __future__ import annotations

import time
import functools

from typing import (
  Any,
  List,
  Dict,
  Optional,
)

from selenium import webdriver

from selenium.common.exceptions import (
  NoSuchElementException,
  InvalidElementStateException,
  ElementNotInteractableException,
  ElementClickInterceptedException,
)

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from errors import (
  ConnectionLimitExceededException,
  TemplateMessageLengthExceededException,
)

from lib.algo import levenshtein

from ..DOM import Cleaner
from ..message import Template
from ..person.person import Person
from ..DOM.javascript import JS
from ..invitation.status import Invitation


class LinkedInSearchConnect(object):
  """Class LinkedInSearchConnect() will search people based on the given Keyword,
  Location, Current Company, School, Industry, Profile Language, First Name,
  Last Name, Title."""
  WAIT: int = 60
  __INVITATION_SENT: int = 0

  def __init__(
          self: LinkedInSearchConnect, driver: webdriver.Chrome, *,
          keyword: str, location: Optional[str] = None,
          title: Optional[str] = None, first_name: Optional[str] = None,
          last_name: Optional[str] = None, school: Optional[str] = None,
          industry: Optional[str] = None,
          current_company: Optional[str] = None,
          profile_language: Optional[str] = None,
          message_template: str = None, use_template: str = None,
          var_template: str = None, grammar_check: bool = True, limit: int = 40) -> None:
    """Constructor method to initialize LinkedInSearchConnect instance.

    :Args:
        - self: {LinkedInSearchConnect} self.
        - driver: {webdriver.Chrome} chromedriver instance.
        - keyword: {str} keyword to search for.
        - location: {str} location to search the keyword in.
        - title: {str} person occupation (Optional).
        - first_name: {str} person first name (Optional).
        - last_name: {str} person last name (Optional).
        - school: {str} person school (Optional).
        - industry: {str} person's industry (Optional).
        - current_company: {str} person's current company (Optional).
        - profile_language: {str} person's profile language (Optional).

    :Raises:
        - {Exception}
        - {ConnectionLimitExceededException}
    """
    if driver is None:
      raise Exception(
        "Expected 'webdriver.Chrome' but received 'NoneType'")
    else:
      self._driver = driver
    if limit > 80:
      raise ConnectionLimitExceededException(
          "Daily invitation limit can't be greater than 80, we recommend 40!")
    else:
      self._limit = limit
    if keyword is None:
      raise Exception("Expected 'str' but received 'NoneType'")
    else:
      self._keyword = keyword
    self._location = location
    self._title = title
    self._first_name = first_name
    self._last_name = last_name
    self._school = school
    self._industry = industry
    self._current_company = current_company
    self._profile_language = profile_language
    self._message_template = message_template
    self._use_template = use_template
    self._grammar_check = grammar_check
    self._var_template = var_template
    self.cleaner = Cleaner(self._driver)

  def _scroll(self: LinkedInSearchConnect) -> None:
    """Private method _scroll() scrolls the page.

    :Args:
        - self: {LinkedInSearchConnect} self

    :Returns:
        - {None}
    """
    js = JS(self._driver)
    old_page_offset = js.get_page_y_offset()
    new_page_offset = js.get_page_y_offset()
    while old_page_offset == new_page_offset:
      js.scroll_bottom()
      time.sleep(1)
      new_page_offset = js.get_page_y_offset()

  def _get_search_results_page(function_: function) -> function:
    @functools.wraps(function_)
    def wrapper(
            self: LinkedInSearchConnect, *args: List[Any],
            **kwargs: Dict[Any, Any]) -> None:
      nonlocal function_
      search_box: webdriver.Chrome = WebDriverWait(
          self._driver, 60).until(
          EC.presence_of_element_located(
              (By.XPATH,
               """//*[@id="global-nav-typeahead"]/input""")))
      try:
        search_box.clear()
      except InvalidElementStateException:  # don't do anything if the element is in read-only state
        pass
      search_box.send_keys(self._keyword)
      search_box.send_keys(Keys.RETURN)
      function_(self, *args, **kwargs)
    return wrapper

  def _execute_cleaners(self: LinkedInSearchConnect) -> None:
    """Method execute_cleaners() scours the unwanted element from the page during the
    connect process.

    :Args:
        - self: {LinkedInConnectionsAuto}

    :Returns:
        - {None}
    """
    self.cleaner.clear_message_overlay()

  def _apply_filters(self: LinkedInSearchConnect):
    def get_element_by_xpath(
            xpath: str, wait: int = None) -> webdriver.Chrome:
      if wait == None:
        wait = LinkedInSearchConnect.WAIT
      return WebDriverWait(self._driver, wait).until(
          EC.presence_of_element_located((By.XPATH, xpath))
      )

    def get_elements_by_xpath(
            xpath: str, wait: int = None) -> webdriver.Chrome:
      if wait == None:
        wait = LinkedInSearchConnect.WAIT
      return WebDriverWait(self._driver, wait).until(
          EC.presence_of_all_elements_located((By.XPATH, xpath))
      )

    people_button = get_element_by_xpath(
        "//div[@id='search-reusables__filters-bar']//button[@aria-label='People']")
    people_button.click()
    del people_button

    if self._location or self._industry or self._profile_language or self._first_name or \
            self._last_name or self._title or self._current_company or self._school:
      filters_button = get_element_by_xpath(
          "//div[@id='search-reusables__filters-bar']//button[@aria-label='All filters']")
      filters_button.click()
      del filters_button

    def check_for_filter(filter: str,
                         filter_dict: Dict[str, webdriver.Chrome],
                         threshold: float = 80.0) -> None:
      """Nested function check_for_filter() checks if the filter option is present or not.

      This function also does some sort of magic using the levenshtein distance algorithm
      to predict the filter option in case the filter given is not present on the filters
      page.

      :Args:
          - filter: {str} Filter option to search for.
          - filter_dict: {Dict[str, webdriver.Chrome]} Hash-map containing filter one side and
              the element to click on, on the other side.
          - threshold: {float} Threshold used by levenshtein distance algorithm to predict for
              a match in case the filter option is not directly present on the filters page.
      """
      nonlocal self
      filters_present: List[str] = filter_dict.keys()

      def click_overlapped_element(element: webdriver.Chrome) -> None:
        """Nested function click_overlapped_element() fixes the WebdriverException:
        Element is not clickable at point (..., ...).

        :Args:
            - element: {webdriver.Chrome} Element.
        """
        nonlocal self
        # @TODO: Validate if the current version of this function is efficient
        self._driver.execute_script("arguments[0].click();", element)

      if isinstance(filter, str):
        if filter in filters_present:
          click_overlapped_element(filter_dict[filter])
          return
        for fltr in filters_present:
          levenshtein_dis = levenshtein(filter, fltr)
          total_str_len = (len(filter) + len(fltr))
          levenshtein_dis_percent = (
              (total_str_len - levenshtein_dis) / total_str_len) * 100
          if levenshtein_dis_percent >= threshold:
            click_overlapped_element(filter_dict[fltr])
        return

      if isinstance(filter, list):
        for fltr in filter:
          if fltr in filters_present:
            click_overlapped_element(filter_dict[fltr])
            continue
          for _fltr in filters_present:
            levenshtein_dis = levenshtein(fltr, _fltr)
            total_str_len = (len(fltr) + len(_fltr))
            levenshtein_dis_percent = (
                (total_str_len - levenshtein_dis) / total_str_len) * 100
            if levenshtein_dis_percent >= threshold:
              click_overlapped_element(filter_dict[_fltr])
        return

    if self._location:
      location_inps = get_elements_by_xpath(
          "//input[starts-with(@id, 'advanced-filter-geoUrn-')]")
      location_labels = get_elements_by_xpath(
          "//label[starts-with(@for, 'advanced-filter-geoUrn-')]")
      locations: List[str] = [
          label.find_element_by_tag_name("span").text
          for label in location_labels]
      # delete location_labels list as soon as we found the location names
      # these objects uses a lot of memory so free them after using them
      del location_labels
      locations_dict: Dict[str, webdriver.Chrome] = {}
      for location, location_inp in zip(locations, location_inps):
        locations_dict[location] = location_inp
      # our primary goal here is to create the location_dict object; once
      # it is created delete the other objects left behind
      del locations
      del location_inps

      check_for_filter(self._location, locations_dict)
      # location_dict again uses a lot of memory so free it after using it
      del locations_dict

    if self._industry:
      industry_inps = get_elements_by_xpath(
          "//input[starts-with(@id, 'advanced-filter-industry-')]")
      industry_labels = get_elements_by_xpath(
          "//label[starts-with(@for, 'advanced-filter-industry-')]")
      industries: List[str] = [
          label.find_element_by_tag_name("span").text
          for label in industry_labels]
      # delete industry_labels list as soon as we found the industry names
      # these objects uses a lot of memory so free them after using them
      del industry_labels
      industries_dict: Dict[str, webdriver.Chrome] = {}
      for industry, industry_inp in zip(industries, industry_inps):
        industries_dict[industry] = industry_inp
      # our primary goal here is to create the industries_dict object; once
      # it is created delete the other objects left behind
      del industries
      del industry_inps

      check_for_filter(self._industry, industries_dict)
      # industries_dict again uses a lot of memory so free it after using it
      del industries_dict

    if self._profile_language:
      profile_language_inps = get_elements_by_xpath(
          "//input[starts-with(@id, 'advanced-filter-profileLanguage-')]")
      profile_language_labels = get_elements_by_xpath(
          "//label[starts-with(@for, 'advanced-filter-profileLanguage-')]")
      profile_languages: List[str] = [
          label.find_element_by_tag_name("span").text
          for label in profile_language_labels]
      # delete profile_language_labels list as soon as we found the industry names
      # these objects uses a lot of memory so free them after using them
      del profile_language_labels
      profile_languages_dict: Dict[str, webdriver.Chrome] = {}
      for profile_language, profile_language_inp in zip(
              profile_languages, profile_language_inps):
        profile_languages_dict[profile_language] = profile_language_inp
      # our primary goal here is to create the profile_languages_dict object; once
      # it is created delete the other objects left behind
      del profile_languages
      del profile_language_inps

      check_for_filter(self._profile_language, profile_languages_dict)
      # profile_languages_dict again uses a lot of memory so free it after using it
      del profile_languages_dict

    if self._first_name:
      first_name_box = get_elements_by_xpath(
          "//label[contains(text(), 'First name')]").find_element_by_tag_name("input")
      first_name_box.clear()
      first_name_box.send_keys(self._first_name)
      # first_name_box element uses a lot of memory as it is a webdriver.Chrome object
      # so delete it
      del first_name_box

    if self._last_name:
      last_name_box = get_element_by_xpath(
          "//label[contains(text(), 'Last name')]").find_element_by_tag_name("input")
      last_name_box.clear()
      last_name_box.send_keys(self._last_name)
      # last_name_box element uses a lot of memory as it is a webdriver.Chrome object
      # so delete it
      del last_name_box

    if self._title:
      title_box = get_element_by_xpath(
          "//label[contains(text(), 'Title')]").find_element_by_tag_name("input")
      title_box.clear()
      title_box.send_keys(self._title)
      # title_box element uses a lot of memory as it is a webdriver.Chrome object
      # so delete it
      del title_box

    if self._current_company:
      company_box = get_element_by_xpath(
          "//label[contains(text(), 'Company')]").find_element_by_tag_name("input")
      company_box.clear()
      company_box.send_keys(self._current_company)
      # company_box element uses a lot of memory as it is a webdriver.Chrome object
      # so delete it
      del company_box

    if self._school:
      school_box = get_element_by_xpath(
          "//label[contains(text(), 'School')]").find_element_by_tag_name("input")
      school_box.clear()
      school_box.send_keys(self._school)
      # school_box element uses a lot of memory as it is a webdriver.Chrome object
      # so delete it
      del school_box

    if self._location or self._industry or self._profile_language or self._first_name or \
            self._last_name or self._title or self._current_company or self._school:
      show_results_button = get_element_by_xpath(
          "//div[@id='artdeco-modal-outlet']//button[@aria-label='Apply current filters to show results']")
      show_results_button.click()
      # show_results_button element uses a lot of memory as it is a webdriver.Chrome object
      # so delete it
      del show_results_button

  def _send_invitation(self: LinkedInSearchConnect) -> None:
    start = time.time()

    p = Person(self._driver)
    persons = p.get_search_results_elements()

    if self._message_template is not None or self._use_template:
      template = Template(self._message_template,
                          use_template=self._use_template,
                          var_template=self._var_template,
                          grammar_check=self._grammar_check)

    invitation = Invitation()
    while True:
      for person in persons:
        if person.connect_button.text == "Pending" or \
                person.connect_button.get_attribute("aria-label") in ("Follow", "Message"):
          continue

        try:
          if self._message_template is None and self._use_template is None:
            ActionChains(self._driver).move_to_element(
                person.connect_button).click().perform()
            send_invite_modal = WebDriverWait(
                self._driver, LinkedInSearchConnect.WAIT).until(
                EC.presence_of_element_located(
                    (By.XPATH,
                     "//div[@aria-labelledby='send-invite-modal']")))
            send_now = send_invite_modal.find_element_by_xpath(
                "//button[@aria-label='Send now']")
            ActionChains(self._driver).move_to_element(
                send_now).click().perform()
          else:
            data = {'name': person.name,
                    'first_name': person.first_name,
                    'last_name': person.last_name,
                    'keyword': self._keyword,
                    'location': person.location,
                    'industry': person.summary, 'title': self._title,
                    'school': self._school,
                    'current_company': self._current_company,
                    'profile_language': self._profile_language,
                    'position': self._title}
            template.set_data(data)
            try:
              message = template.read()
            except TemplateMessageLengthExceededException:
              message = "Hi there,\nI'm in a personal mission of expanding my network with professionals\nLet's connect"
            ActionChains(self._driver).move_to_element(
                person.connect_button).click().perform()
            send_invite_modal = WebDriverWait(
                self._driver, LinkedInSearchConnect.WAIT).until(
                EC.presence_of_element_located(
                    (By.XPATH,
                     "//div[@aria-labelledby='send-invite-modal']")))
            add_note = send_invite_modal.find_element_by_xpath(
                "//button[@aria-label='Add a note']")
            ActionChains(self._driver).move_to_element(
              add_note).click().perform()
            custom_message = send_invite_modal.find_element_by_xpath(
                "//textarea[@id='custom-message']")
            try:
              custom_message.clear()
            except InvalidElementStateException:  # don't do anything if the element is in read-only state
              pass
            custom_message.send_keys(message)
            send_now = send_invite_modal.find_element_by_xpath(
                "//button[@aria-label='Send now']")
            ActionChains(self._driver).move_to_element(
                send_now).click().perform()
          invitation.set_invitation_fields(
              name=person.name, occupation=person.occupation,
              status="sent", elapsed_time=time.time() - start)
          invitation.status(come_back_by=9)
          LinkedInSearchConnect.__INVITATION_SENT += 1
        except (ElementNotInteractableException,
                ElementClickInterceptedException) as exc:
          if isinstance(exc, ElementClickInterceptedException):
            break
          invitation.set_invitation_fields(
              name=person.name, occupation=person.occupation,
              status="failed", elapsed_time=time.time() - start)
          invitation.status(come_back_by=9)

        if LinkedInSearchConnect.__INVITATION_SENT == self._limit:
          break

      def next_() -> None:
        next_: webdriver.Chrome = self._driver.find_element_by_xpath(
            "//main[@id='main']//button[@aria-label='Next']")
        ActionChains(self._driver).move_to_element(
          next_).click().perform()

      try:
        next_()
      except NoSuchElementException:
        self._scroll()
        next_()
      persons = p.get_search_results_elements()

  @_get_search_results_page
  def run(self: LinkedInSearchConnect) -> None:
    """Method run() calls the send_invitation method, but first it assures that the object
    self has driver property in it.

    :Args:
        - self: {LinkedInConnectionsAuto} object

    :Returns:
        - {None}
    """
    self._apply_filters()
    self._execute_cleaners()
    self._send_invitation()

  def __del__(self: LinkedInSearchConnect) -> None:
    """LinkedInConnectionsAuto destructor to de-initialise LinkedInConnectionsAuto object.

    :Args:
        - self: {LinkedInConnectionsAuto} object

    :Returns:
        - {None}
    """
    LinkedInSearchConnect.__INVITATION_SENT = 0
    try:
      self._driver.quit()
    except AttributeError:
      # this mean that the above code produces some error while running and
      # driver instance died
      pass
