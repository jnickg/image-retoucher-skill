# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
import logging
from click import prompt
from dateutil.parser import isoparse as parse_date
import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model.ui.simple_card import SimpleCard

from ask_sdk_model import Response
from requests import session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ATTR_TIME_SLOT = "TimeSlot"
ATTR_SESSION_IMAGE = "SessionImage"
ATTR_REALLY_LOAD_NEW_IMAGE = "ReallyLoadNewImage"

class SessionImageDescriptor:
    loaded:bool = True
    url:str = "https://voice-retouch-rest.herokuapp.com/todo/integrate/with/rest/api"


def initialize_handler_attributes(handler_input:HandlerInput) -> None:
    handler_input.attributes_manager.persistent_attributes[ATTR_REALLY_LOAD_NEW_IMAGE] = False


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Welcome to Image Retoucher! You can load a photo to edit, or if your device is showing one now, you can start editing."
        prompt_output = "What would you like to do?"

        initialize_handler_attributes(handler_input)

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(prompt_output)
                .response
        )


class EditImageIntentHandler(AbstractRequestHandler):
    """Handler for Edit Image Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("EditImageIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        slots = handler_input.request_envelope.request.intent.slots
        photo_synonym = slots["PhotoSlot"].value
        time_str = slots["TimeSlot"].value

        session_image: SessionImageDescriptor = handler_input.attributes_manager.persistent_attributes[ATTR_SESSION_IMAGE]
        really_load:bool = handler_input.attributes_manager.persistent_attributes[ATTR_REALLY_LOAD_NEW_IMAGE]
        if (session_image is None or really_load):
            speak_output = f"Alright, let's load one {photo_synonym} to edit. Looking for photos taken {time_str}..."
            prompt_output = "If you see the photo you want to edit, say \"Edit image X\" where X is the label you see. Otherwise, say \"Keep Browsing\". For now, hearing this response means an image is loaded."
            time = parse_date(time_str)
            card = SimpleCard(title="Photo Selection", content=f"TODO render card image to display photos taken\r\nat {time}, for user to select.")
            handler_input.attributes_manager.persistent_attributes[ATTR_TIME_SLOT] = time
            handler_input.attributes_manager.persistent_attributes[ATTR_SESSION_IMAGE] = SessionImageDescriptor()
            handler_input.attributes_manager.persistent_attributes[ATTR_REALLY_LOAD_NEW_IMAGE] = False
        else:
            speak_output = "It looks like you're already editing an image. If you really want to edit a new photo, just confirm by asking again."
            prompt_output = speak_output
            card = SimpleCard(title="Confirm", content="Really edit a new photo?")
        

        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_card(card)
                .ask(prompt_output)
                .response
        )


class EditSliderMetricIntentHandler(AbstractRequestHandler):
    """Handler for Edit Slider Metric Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("EditSliderMetricIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        slots = handler_input.request_envelope.request.intent.slots
        metric = slots["MetricSlot"].value

        session_image: SessionImageDescriptor = handler_input.attributes_manager.persistent_attributes[ATTR_SESSION_IMAGE]
        if (session_image is not None and session_image.loaded):
            speak_output = f"Alright, let's edit this photo's {metric}."
            prompt_output = "Just say \"higher\" or \"lower\" and I'll adjust the slider a bit less each time. You can say \"done\" when you're satisfied, or \"cancel.\""
            card = SimpleCard(title="Photo Editing", content="TODO render selected image in current state w/ histogram so user can see it")
        else:
            speak_output = "Sorry, I don't have a loded image in this session. Try saying \"edit a photo from today\" or another time"
            prompt_output = speak_output
            card = SimpleCard(title="Error", content="No loaded image in current session.")

        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_card(card)
                .ask(prompt_output)
                .response
        )


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "You can load a photo to edit, or if your device is showing one now, you can start editing."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Goodbye!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # TODO end REST API session with a DELETE request on the image.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(EditImageIntentHandler())
sb.add_request_handler(EditSliderMetricIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()