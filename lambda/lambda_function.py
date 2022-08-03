# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
import logging
from multiprocessing.sharedctypes import Value
from urllib import response
from dataclasses import dataclass, field, asdict
from typing import List
from pathlib import Path
import json
import urllib3

import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model.ui.simple_card import SimpleCard
from ask_sdk_model.ui.standard_card import StandardCard
from ask_sdk_model.ui.image import Image

from ask_sdk_model import Response, Slot
from requests import Session, session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

http = urllib3.PoolManager()

class IRError(Exception):
    def __init__(self, message: str, *args, **kwargs):
        super().__init__(args)
        self.message = message
        self.kwargs = kwargs
    def __str__(self) -> str:
        return self.message

API_PROTOCOL = 'https://'
API_ROOT_URL = Path('image-retoucher-rest.herokuapp.com/api/')
API_IMAGE_SLUG = Path('image')
API_COLLAGE_URL = API_PROTOCOL + str(API_ROOT_URL / API_IMAGE_SLUG / 'static/collage')
API_COMPARISON_SLUG = Path('comparison')
API_SMALL_SLUG = Path('small')

SLOT_PHOTO = 'PhotoSlot'
SLOT_ID = 'IDSlot'
SLOT_ID2 = 'IDSlot2'
SLOT_METRIC = 'MetricSlot'
SLOT_METRIC_VALUE = 'MetricValueSlot'
SLOT_ALGO_NAME = 'AlgoNameSlot'

METRIC_OPNAMES_MAP = {
    'contrast': 'contrast',
    'exposure': 'exposure',
    'brightness': 'exposure',
    'saturation': 'saturation',
    'vibrance': 'saturation',
    'color intensity': 'saturation',
    'tint': 'tint',
    'hue': 'tint'
}

ALGO_NAME_CLAHE = 'histogram equalization'
ALGO_NAME_CLRXFR = 'color transfer'

ALGO_OPNAMES_MAP = {
    'contrast limited adaptive histogram equalization': 'clahe',
    'histogram equalization': 'clahe',
    'clahe': 'clahe',
    'pizer': 'clahe',
    'color transfer': 'colorxfer',
    'reinhard': 'colorxfer',
    'tone transfer': 'colorxfer',
    'tone mapping': 'colorxfer'
}

def is_algo_name_val_colorxfer(algo_name: str) -> bool:
    return ALGO_OPNAMES_MAP.get(algo_name, 'nop') == 'colorxfer'


ATTR_SESSION_CONTEXT = 'SessionContext'

@dataclass
class OperationDescriptor:
    op : str = ''
    val : int = ''

@dataclass
class SessionContext:
    image_id : int = None
    image_url : str = None
    really_change : bool = False
    operations : List[OperationDescriptor] = field(default_factory=list)

ATTR_TIME_SLOT = "TimeSlot"
ATTR_SESSION_IMAGE = "SessionImage"

def get_context(handler_input:HandlerInput) -> SessionContext:
    cxt_json = handler_input.attributes_manager.session_attributes[ATTR_SESSION_CONTEXT]
    cxt = SessionContext(**json.loads(cxt_json))
    ops = []
    for o in cxt.operations:
        ops.append(OperationDescriptor(**o))
    cxt.operations = ops

    logger.info(f'Deserializing context: {cxt_json} -> {cxt}')
    return cxt

def set_context(handler_input:HandlerInput, cxt:SessionContext):
    cxt_json = json.dumps(asdict(cxt))
    logger.info(f'Serializing context: {cxt} -> {cxt_json}')
    handler_input.attributes_manager.session_attributes[ATTR_SESSION_CONTEXT] = cxt_json

def initialize_handler_attributes(handler_input:HandlerInput) -> None:
    set_context(handler_input, SessionContext())

def is_url_valid(url):
    logger.info(f'Testing validity of URL {url}')
    return http.request("GET", url).status < 400

def build_image_url(cxt: SessionContext, comparison:bool = False) -> str:
    full_url : str = cxt.image_url
    for op in cxt.operations:
        full_url += f'/{op.op}/{op.val}'
    if comparison:
        full_url += f'/{API_COMPARISON_SLUG}'
    logger.info(f'Built full URL: {full_url}')
    return full_url

def update_operation(cxt: SessionContext, opname: str, opval: int) -> SessionContext:
    updated = False
    for op in cxt.operations:
        if op.op == opname:
            op.val = opval
            updated = True
    if not updated: cxt.operations.append(OperationDescriptor(op=opname, val=opval))
    logger.info(f'Updated context: {cxt}')
    return cxt

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speak_output = "Welcome to Image Retoucher! You can select a photo to edit, or if your device is showing one now, you can start editing."
        prompt_output = "What would you like to do?"

        logger.info('Initializing handler attributes')
        initialize_handler_attributes(handler_input)
        logger.info('Sending response...')

        card = StandardCard(
            title = 'Image Retoucher',
            text = 'Select an image from the card to edit, using the number next to it.',
            image = Image(large_image_url=str(API_COLLAGE_URL))
        )
        handler_input.response_builder.speak(speak_output)
        handler_input.response_builder.set_card(card)
        handler_input.response_builder.ask(prompt_output)
        return handler_input.response_builder.response


class EditImageIntentHandler(AbstractRequestHandler):
    """Handler for Edit Image Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("EditImageIntent")(handler_input)

    def _update_context_and_return_outputs(self, context: SessionContext, image_id: any):
        if image_id is None:
            speak_output = f"Alright, let's edit a photo."
            prompt_output = "If you see the photo you want to edit, say \"Edit image X\" where X is the label you see."
            card = StandardCard(
                title = 'Photo Selection',
                text = 'Select an image from the card to edit, using the number next to it.',
                image = Image(large_image_url=API_COLLAGE_URL)
            )
        else:
            speak_output = f"Alright, let's edit photo {image_id}"
            new_url = API_PROTOCOL + str(API_ROOT_URL / API_IMAGE_SLUG / str(image_id))
            if is_url_valid(str(new_url)):
                context.image_id = int(image_id)
                context.image_url = new_url
                card = StandardCard(
                    title = f'Now Editing Photo {context.image_id}',
                    text = 'Proceed to edit image parameters or apply algorithms',
                    image = Image(large_image_url=context.image_url)
                )
                prompt_output = "Go ahead and start editing. For example, you can say 'set exposure to 30' or 'apply histogram equalization.'"
            else:
                raise IRError("That image ID didn't work.", show_collage=True, card_message="Try saying 'Edit image 0'", prompt="Which image would you like to load? Pick an ID from the collage.")
        return speak_output, prompt_output, card

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        photo_synonym = slots["PhotoSlot"].value
        image_id = slots[SLOT_ID].value

        context = get_context(handler_input)
        if (context.image_id is None or context.image_url is None) or (len(context.operations) == 0) or context.really_change:
            speak_output, prompt_output, card = self._update_context_and_return_outputs(context, image_id)
            context.operations.clear()
            context.really_change = False
        else:
            speak_output = "It looks like you're already editing an image.\r\nIf you really want to edit a new photo, just confirm by asking again."
            prompt_output = speak_output
            context.really_change = True
            card = SimpleCard(title="Confirm", content="Really edit a new photo?")

        set_context(handler_input, context)
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
        metric = slots[SLOT_METRIC].value

        context = get_context(handler_input)
        if (context.image_url is not None):
            speak_output = f"Alright, let's edit this photo's {metric}."
            prompt_output = "Just say \"higher\" or \"lower\" and I'll adjust the slider a bit less each time. You can say \"done\" when you're satisfied, or \"cancel.\""
            card = SimpleCard(title="Photo Editing", content="TODO render selected image in current state w/ histogram so user can see it")
        else:
            speak_output = "Sorry, I don't have a loded image in this session. Try saying \"edit a photo from today\" or another time"
            prompt_output = speak_output
            card = SimpleCard(title="Error", content="No loaded image in current session.")

        set_context(handler_input, context)
        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_card(card)
                .ask(prompt_output)
                .response
        )


class SetSliderMetricIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input) -> bool:
        return ask_utils.is_intent_name("SetSliderMetricIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        slots = handler_input.request_envelope.request.intent.slots
        metric_repeat = slots[SLOT_METRIC].value
        metric = METRIC_OPNAMES_MAP.get(str(metric_repeat), 'nop')
        value = slots[SLOT_METRIC_VALUE].value
        value = int(value) if value is not None else 0
        logger.info(f'Setting {metric} ({type(metric)} to {value} ({type(value)})')

        if value < -100 or value > 100:
            raise IRError(f"Sorry, but I don't know how to apply a value of {value}. Try using a range of negative one hundred to positive one hundred, where zero means 'no change.'")


        context = get_context(handler_input)
        if (context.image_url is not None):
            speak_output = f"Alright, setting {metric} to {value}."
            prompt_output = speak_output
            context = update_operation(context, str(metric), int(value))
            new_url = build_image_url(context)
            card = StandardCard(
                title = f'Updated Photo {context.image_id}',
                text = f'{metric_repeat} is now {value}',
                image = Image(large_image_url=new_url)
            )
        else:
            speak_output = "Sorry, I don't have a loded image in this session. Try saying \"edit photo 0\" or another time"
            prompt_output = speak_output
            card = SimpleCard(title="Error", content="No loaded image in current session.")

        set_context(handler_input, context)
        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_card(card)
                .ask(prompt_output)
                .response
        )

class ApplyAlgorithmIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input) -> bool:
        return ask_utils.is_intent_name("ApplyAlgorithmIntent")(handler_input)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        algo_name = slots[SLOT_ALGO_NAME].value
        param = slots[SLOT_ID].value
        context = get_context(handler_input)

        algo_name = str(algo_name).lower()
        if is_algo_name_val_colorxfer(str(algo_name)) and param is None:
            # TODO show collage card and prompt for image ID instead of raising error
            raise IRError("Please specify which image ID you want to use with color transfer", show_collage=True, card_message="Try saying 'apply color transfer using image 0'", prompt="Try saying 'apply color transfer using image 0' or another ID you see here.")
        if (context.image_url is None):
            raise IRError("Sorry, I don't have a loded image in this session", show_collage=True, prompt="Try saying 'edit photo 0' or another ID you see here.")

        param = param if param is not None else 0
        algo_op = ALGO_OPNAMES_MAP.get(str(algo_name), 'nop')
        context = update_operation(context, str(algo_op), int(param))
        new_url = build_image_url(context)
        speak_output = f"Alright, applying {algo_name} to the image."
        prompt_output = speak_output
        card = StandardCard(
            title = f'Updated Photo {context.image_id}',
            text = f'Applied {algo_name} to image',
            image = Image(large_image_url=new_url)
        )

        set_context(handler_input, context)
        return (
            handler_input.response_builder
               .speak(speak_output)
               .set_card(card)
               .ask(prompt_output)
               .response
        )

class UndoChangesIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input) -> bool:
        return ask_utils.is_intent_name("UndoChangesIntent")(handler_input)

    def handle(self, handler_input):
        context = get_context(handler_input)

        if (context.image_url is None):
            raise IRError("Sorry, I don't have a loded image in this session", show_collage=True, prompt="Try saying 'edit photo 0' or another ID you see here.")
        if (len(context.operations) == 0):
            raise IRError("Hmm, there's nothing to undo", prompt="Try saying 'set brightness to 25'")

        op = context.operations.pop()
        speak_output = f'OK, reverting the last change, which was {op.op}'
        new_url = build_image_url(context)
        card = StandardCard(
            title = f'Updated Photo {context.image_id}',
            text = f'Undid change: {op.op}',
            image = Image(large_image_url=new_url)
        )

        set_context(handler_input, context)
        return (
            handler_input.response_builder
               .speak(speak_output)
               .set_card(card)
               .ask(speak_output)
               .response
        )

class SaveImageIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input) -> bool:
        return ask_utils.is_intent_name("SaveImageIntent")(handler_input)

    def handle(self, handler_input):
        context = get_context(handler_input)

        # TODO DO
        speak_output = "I don't know how to do this yet."

        set_context(handler_input, context)
        return (
            handler_input.response_builder
               .speak(speak_output)
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
        prompt_output = speak_output
        card = None
        if isinstance(exception, IRError):
            speak_output = exception.message
            if 'prompt' in exception.kwargs:
                prompt_output = exception.kwargs['prompt']

            if 'show_collage' in exception.kwargs and exception.kwargs['show_collage']:
                card = StandardCard(
                    title = 'Image Retoucher',
                    text = 'Showing collage' if 'card_message' not in exception.kwargs else exception.kwargs['card_message'],
                    image = Image(large_image_url=str(API_COLLAGE_URL))
                )
        else:
            speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        handler_input.response_builder.speak(speak_output)
        handler_input.response_builder.ask(prompt_output)
        if card is not None:
            handler_input.response_builder.set_card(card)
        return handler_input.response_builder.response

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(EditImageIntentHandler())
sb.add_request_handler(EditSliderMetricIntentHandler())
sb.add_request_handler(SetSliderMetricIntentHandler())
sb.add_request_handler(ApplyAlgorithmIntentHandler())
sb.add_request_handler(UndoChangesIntentHandler())
sb.add_request_handler(SaveImageIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()