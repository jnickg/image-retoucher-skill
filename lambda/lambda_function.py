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
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal
from abc import abstractmethod
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
from ask_sdk_model.ui.play_behavior import PlayBehavior

from ask_sdk_model import Response, Slot
from requests import Session, session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

http = urllib3.PoolManager()

class IRError(Exception):
    """
    Base error type for Image Retoucher. Contains rich information about what went wrong, so a
    custom handler (below) can display useful feedback to the end user.
    """
    def __init__(self, message: str, *args, **kwargs):
        super().__init__(args)
        self.message = message
        """
        The message to be logged and told to the user.
        """

        self.kwargs = kwargs
        """
        A collection of keyword arguments consumed when this type generates outputs for the user.
        """

    def __str__(self) -> str:
        return self.message

    def get_outputs(self):
        """
        Generates speak, prompt, and card outputs for the Alexa device to share with the user.
        The contents of those outputs depend on the data stored in this error type, and any flags
        set in its keyword arguments.
        """

        speak_output = self.message
        if 'say_metric_help' in self.kwargs and self.kwargs['say_metric_help']:
            speak_output += '(By the way, valid metric values are: exposure, contrast, tint, and saturation.) '
        if 'say_algorithn_help' in self.kwargs and self.kwargs['say_algorithn_help']:
            speak_output += '(Also, valid algorithms are histogram equalization, color transfer, H.D.R., sharpen filter, summer filter, winter filter, and grayscale filter.) '
        prompt_output = ""
        card = None
        if 'prompt' in self.kwargs:
            prompt_output = self.kwargs['prompt']
        if 'show_collage' in self.kwargs and self.kwargs['show_collage']:
            card = StandardCard(
                title = 'Image Retoucher',
                text = 'Showing collage' if 'card_message' not in self.kwargs else self.kwargs['card_message'],
                image = Image(large_image_url=str(API_COLLAGE_URL))
            )
        return speak_output, prompt_output, card

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

ALGO_OPNAMES_MAP = {
    'contrast limited adaptive histogram equalization': 'clahe',
    'histogram equalization': 'clahe',
    'clahe': 'clahe',
    'pizer': 'clahe',
    'color transfer': 'colorxfer',
    'reinhard': 'colorxfer',
    'tone transfer': 'colorxfer',
    'tone mapping': 'colorxfer',
    'warm filter': 'summer',
    'summer filter': 'summer',
    'summer': 'summer',
    'cool filter': 'winter',
    'winter filter': 'winter',
    'winter': 'winter',
    'high dynamic range': 'hdr',
    'hdr': 'hdr',
    'sharpen': 'sharpen',
    'sharpening': 'sharpen',
    'sharp filter': 'sharpen',
    'sharpen filter': 'sharpen',
    'sharpening filter': 'sharpen',
    'grayscale': 'gray',
    'grayscale filter': 'gray',
    'gray': 'gray',
    'color2gray': 'gray',
    'color to gray': 'gray'
}

OPNAME_TO_FRIENDLY_MAP = {
    'clahe': 'histogram equalization',
    'colorxfer': 'color transfer',
    'hdr': 'h.d.r',
    'gray': 'grayscale filter',
    'winter': 'winter filter',
    'summer': 'summer filter',
}

END_INTERACTIVE_HELP = "When you're satisfied, go ahead and say 'save edits' or 'commit changes.' "

def is_algo_name_val_colorxfer(algo_name: str) -> bool:
    return ALGO_OPNAMES_MAP.get(algo_name, 'nop') == 'colorxfer'


ATTR_SESSION_CONTEXT = 'SessionContext'

@dataclass
class OperationDescriptor:
    """
    A simple, serializable descriptor of an operation occurring on an image. Used to build URLs
    """

    op : str = ''
    """
    The name of the operation
    """

    val : int = 0
    """
    The parameter associated with this operation. Depending on the operation, this value may be
    ignored.
    """

@dataclass
class SessionContext:
    """
    The stateful context for a user's editing session. Contains all state data, and includes many
    helper functions for intent handlers to use.
    """

    image_id : int = None
    """
    The numerical ID of the image currently being edited, or None if no image is being edited.
    """

    image_url : str = None
    """
    The base URL of the iamge currently being edited. Used to build URLs with operations
    """

    confirmed_change_image : bool = False
    """
    Confirmation flag for changing the currently-edited image
    """

    in_interactive_edit : bool = False
    """
    Whether we are in an interactive edit mode for some slider.
    """

    interactive_edit_metric : str = ''
    """
    The name of the slider currently being edited interactively, or None
    """

    interactive_edit_from_existing_op : bool = False
    """
    Whether this interactive editing session is modifying a slider that had already been set
    earlier in the overall editing session.
    """

    interactive_edit_first_val : int = 0
    """
    The first value that was set during this interactive editing session. Used when cancelling
    to restore an existing operation.
    """

    interactive_edit_last_val : int = 0
    """
    The last value that was set after an adjustment.
    """

    interactive_edit_last_adjustment : int = 0
    """
    The magnitude of the last adjustment.
    """

    interactive_edit_last_adjustment_dir : Literal['up', 'down', 'none'] = 'none'
    """
    The direction of the last adjustment. 'none' means the editing session just started.
    """

    interactive_edit_fine_tuning_prompt_done : bool = False
    """
    Whether the last change(s) were minor enough that Alexa already prompted the user about how to finish.
    """

    operations : List[OperationDescriptor] = field(default_factory=list)
    """
    A list (treated like a stack) of operations being run on the base image
    """

    def build_image_url(self, comparison:bool=False):
        """
        Using the context's current state, and any specified flags, builds a valid image URL to render the image.
        """
        full_url : str = self.image_url
        for op in self.operations:
            full_url += f'/{op.op}/{op.val}'
        if self.in_interactive_edit:
            full_url += f'/{self.interactive_edit_metric}/{self.interactive_edit_last_val}'
        if comparison:
            full_url += f'/{API_COMPARISON_SLUG}'
        logger.info(f'Built full URL: {full_url}')
        return full_url

    def add_operation(self, opname: str, opval: int):
        """
        Adds a new operation to the context's operation stack, to apply to the currently-edited image.
        """
        if opname not in set(METRIC_OPNAMES_MAP.values()) and opname not in set(ALGO_OPNAMES_MAP.values()):
            raise IRError(f"Sorry, I don't recognize {opname}. You can apply an algorithm, or you can set or adjust a metric.", say_metric_help=True, say_algorithn_help = True)
        
        latest_op = OperationDescriptor(op=opname, val=opval)

        existing_opnames = [op.op for op in self.operations]
        if opname in existing_opnames:
            existing_op_idx = existing_opnames.index(opname)
            existing_op = self.operations.pop(existing_op_idx)
            logger.info(f'Updating {existing_op} to {latest_op}')

        self.operations.append(latest_op)
        logger.info(f"Latest operation: {latest_op}")

    def enter_interactive_mode(self, metric:str):
        """
        Enters interactive slider editing mode.
        """
        if self.in_interactive_edit:
            self.exit_interactive_mode('cancel')
        self.in_interactive_edit = True
        if metric not in set(METRIC_OPNAMES_MAP.values()):
            raise IRError('Unrecognized metric for interactive edit mode.', say_metric_help=True)
        self.interactive_edit_metric = metric
        self.interactive_edit_last_adjustment = 0
        self.interactive_edit_last_adjustment_dir = 'none'
        self.interactive_edit_fine_tuning_prompt_done = False
        self.interactive_edit_last_val = 0
        self.interactive_edit_first_val = 0
        existing_opnames = [op.op for op in self.operations]
        if metric in existing_opnames:
            self.interactive_edit_from_existing_op = True
            existing_op_idx = existing_opnames.index(metric)
            existing_op = self.operations.pop(existing_op_idx)
            self.interactive_edit_last_val = existing_op.val
            self.interactive_edit_first_val = existing_op.val

    def exit_interactive_mode(self, what_do:Literal['confirm', 'cancel']):
        """
        Exits interactive slider editing mode, restoring the image to the last state.
        """
        if not self.in_interactive_edit:
            return
        if what_do == 'confirm':
            self.add_operation(self.interactive_edit_metric, self.interactive_edit_last_val)
        elif what_do == 'cancel' and self.interactive_edit_from_existing_op:
            self.add_operation(self.interactive_edit_metric, self.interactive_edit_first_valr)

        self.interactive_edit_metric = ''
        self.interactive_edit_first_val = 0
        self.interactive_edit_last_val = 0
        self.interactive_edit_last_adjustment = 0
        self.interactive_edit_last_adjustment_dir = 'none'
        self.interactive_edit_fine_tuning_prompt_done = False
        self.in_interactive_edit = False

    def build_interactive_card(self):
        """
        Builds the card used during interactive editing sessions
        """
        if not self.in_interactive_edit:
            raise IRError("Something went wrong: I can't build an interactive adjustment card when we're not interactively adjusting a metric.")
        new_url = self.build_image_url(comparison=True)
        card = StandardCard(
            title = f'Updated Photo {self.image_id}',
            text = f'Adjusting {self.interactive_edit_metric} by {self.interactive_edit_last_adjustment}',
            image = Image(large_image_url=new_url)
        )
        return card


def is_url_valid(url):
    logger.info(f'Testing validity of URL {url}')
    return http.request("GET", url).status < 400

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speak_output = "Welcome to Image Retoucher! You can select a photo to edit, or if your device is showing one now, you can start editing."
        prompt_output = "What would you like to do?"

        logger.info('Initializing handler attributes')
        IRRequestHandler.set_context(handler_input, SessionContext())
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


class IRRequestHandler(AbstractRequestHandler):
    @staticmethod
    def get_context(handler_input:HandlerInput) -> SessionContext:
        cxt_json = handler_input.attributes_manager.session_attributes[ATTR_SESSION_CONTEXT]
        cxt = SessionContext(**json.loads(cxt_json))
        ops = []
        for o in cxt.operations:
            ops.append(OperationDescriptor(**o))
        cxt.operations = ops

        logger.info(f'Deserializing context: {cxt_json} -> {cxt}')
        return cxt

    @staticmethod
    def set_context(handler_input:HandlerInput, cxt:SessionContext):
        cxt_json = json.dumps(asdict(cxt))
        logger.info(f'Serializing context: {cxt} -> {cxt_json}')
        handler_input.attributes_manager.session_attributes[ATTR_SESSION_CONTEXT] = cxt_json


    @abstractmethod
    def can_handle_inner(self, handler_input: HandlerInput, context: SessionContext) -> bool:
        pass
    def can_handle(self, handler_input: HandlerInput) -> bool:
        context = IRRequestHandler.get_context(handler_input)
        try:
            can_handle = self.can_handle_inner(handler_input, context)
            return can_handle
        finally:
            IRRequestHandler.set_context(handler_input, context)

    @abstractmethod
    def handle_inner(self, handler_input: HandlerInput, context: SessionContext) -> Response:
        pass
    def handle(self, handler_input: HandlerInput) -> Response:
        context = IRRequestHandler.get_context(handler_input)
        try:
            response = self.handle_inner(handler_input, context)
            return response
        finally:
            IRRequestHandler.set_context(handler_input, context)

class EditImageIntentHandler(IRRequestHandler):
    """Handler for Edit Image Intent."""
    def can_handle_inner(self, handler_input, context):
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

    def handle_inner(self, handler_input, context):
        slots = handler_input.request_envelope.request.intent.slots
        image_id = slots[SLOT_ID].value

        if (context.image_id is None and context.image_url is None) or (len(context.operations) == 0) or context.confirmed_change_image:
            speak_output, prompt_output, card = self._update_context_and_return_outputs(context, image_id)
            context.operations.clear()
            context.confirmed_change_image = False
        elif context.in_interactive_edit:
            raise IRError("You're currently interactively editing a slider. To edit a new image, first say 'cancel'")
        else:
            context.confirmed_change_image = True
            speak_output = "It looks like you're already editing an image."
            prompt_output = "If you really want to edit a new photo, just confirm by asking again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_card(card)
                .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
                .response
        )


class EditSliderMetricIntentHandler(IRRequestHandler):
    """Handler for Edit Slider Metric Intent."""
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_intent_name("EditSliderMetricIntent")(handler_input)

    def handle_inner(self, handler_input, context):
        slots = handler_input.request_envelope.request.intent.slots
        metric_repeat = slots[SLOT_METRIC].value
        metric = METRIC_OPNAMES_MAP.get(str(metric_repeat), 'nop')

        if (context.image_url is not None):
            context.enter_interactive_mode(str(metric))
            speak_output = f"Alright, let's edit this photo's {metric}."
            prompt_output = "Just say \"higher\" or \"lower\" and I'll adjust the slider a bit less each time. You can say \"done\" when you're satisfied, or \"cancel.\""
            card = context.build_interactive_card()
        elif context.in_interactive_edit:
            raise IRError("You're already interactively editing a slider. To interactively edit another slider, first say 'cancel'")
        else:
            raise IRError("Hmm... You probably meant to edit an image, but I'm just an A.I. and I misunderstood. Try saying \"edit photo 3\" or any zero to nine value, to load an image.", show_collage=True)

        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_card(card)
                .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
                .response
        )


class SetSliderMetricIntentHandler(IRRequestHandler):
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_intent_name("SetSliderMetricIntent")(handler_input)

    @staticmethod
    def set_slider_metric(handler_input: HandlerInput, context: SessionContext) -> Response:
        slots = handler_input.request_envelope.request.intent.slots
        metric_repeat = slots[SLOT_METRIC].value
        metric = METRIC_OPNAMES_MAP.get(str(metric_repeat), 'nop')
        value = slots[SLOT_METRIC_VALUE].value
        value = int(value) if value is not None else 0
        logger.info(f'Setting {metric} ({type(metric)} to {value} ({type(value)})')

        if value < -100 or value > 100:
            raise IRError(f"Sorry, but I don't know how to apply a value of {value}. Try using a range of negative one hundred to positive one hundred, where zero means 'unchanged from original.'")
        if context.image_url is None:
            raise IRError("Sorry, I don't have a loded image in this session. Try saying \"edit photo 0\" or another time", show_collage=True)

        if context.in_interactive_edit:
            context.interactive_edit_last_adjustment = abs(value - context.interactive_edit_last_val)
            context.interactive_edit_last_adjustment_dir = (
                'down' if value < context.interactive_edit_last_val else
                'up' if value > context.interactive_edit_last_val else
                'none'
            )
            context.interactive_edit_last_val = value
            if context.interactive_edit_last_adjustment_dir != 'none':
                speak_output = f'OK, moving {context.interactive_edit_metric} {context.interactive_edit_last_adjustment_dir }. '
            else:
                speak_output = f"OK, setting {context.interactive_edit_metric}. "

            if context.interactive_edit_last_val >= 100:
                context.interactive_edit_last_val = 100
                speak_output += "This is as high as it can go. "
            if context.interactive_edit_last_val <= -100:
                context.interactive_edit_last_val = -100
                speak_output += "This is as low as it can go. "

            if context.interactive_edit_last_adjustment < 10 and not context.interactive_edit_fine_tuning_prompt_done:
                speak_output += f"Looks like you're fine tuning now. {END_INTERACTIVE_HELP}"
                context.interactive_edit_fine_tuning_prompt_done = True

            prompt_output = "How does it look?"
            card = context.build_interactive_card()
        else:
            speak_output = f"Alright, setting {metric} to {value}."
            prompt_output = ""
            context.add_operation(str(metric), int(value))
            new_url = context.build_image_url()
            card = StandardCard(
                title = f'Updated Photo {context.image_id}',
                text = f'{metric_repeat} is now {value}',
                image = Image(large_image_url=new_url)
            )

        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_card(card)
                .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
                .response
        )

    def handle_inner(self, handler_input, context):
        return SetSliderMetricIntentHandler.set_slider_metric(handler_input, context)

class ApplyAlgorithmIntentHandler(IRRequestHandler):
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_intent_name("ApplyAlgorithmIntent")(handler_input)

    def handle_inner(self, handler_input, context):
        slots = handler_input.request_envelope.request.intent.slots
        algo_name = slots[SLOT_ALGO_NAME].value
        param = slots[SLOT_ID].value

        if context.image_url is None:
            raise IRError("Hmm, we're not yet editing an image, so I can't apply an algorithm.", show_collage=True)
        if context.in_interactive_edit:
            raise IRError("You're currently interactively editing a slider. To apply an algorithm instead, first say 'cancel'")

        algo_name = str(algo_name).lower()
        if is_algo_name_val_colorxfer(str(algo_name)) and param is None:
            raise IRError("Whoops. Please specify which image ID you want to use with color transfer. Try saying 'apply color transfer using image 0' or another ID you see here. ",
                          card_message="Try saying 'apply color transfer using image 0'", 
                          show_collage=True)

        param = param if param is not None else 0
        algo_op = ALGO_OPNAMES_MAP.get(str(algo_name), 'nop')
        if (algo_op == 'nop'):
            raise IRError("Sorry, I don't know that algorithm. ", say_algorithn_help=True)

        context.add_operation(str(algo_op), int(param))
        new_url = context.build_image_url()
        speak_output = f"Alright, applying {algo_name} to the image."
        prompt_output = ""
        card = StandardCard(
            title = f'Updated Photo {context.image_id}',
            text = f'Applied {algo_name} to image',
            image = Image(large_image_url=new_url)
        )

        return (
            handler_input.response_builder
               .speak(speak_output)
               .set_card(card)
               .ask(prompt_output)
               .response
        )

class UndoChangesIntentHandler(IRRequestHandler):
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_intent_name("UndoChangesIntent")(handler_input)

    def handle_inner(self, handler_input, context):
        if (context.image_url is None):
            raise IRError(message="Sorry, I don't have a loded image in this session. ",
                          prompt="Try saying 'edit photo 0' or another ID you see here. ",
                          show_collage=True)
        if context.in_interactive_edit:
            raise IRError("Right now I don't support undo during interactive edits. ",
                          prompt="If you don't like the changes right now, just cancel and try again. If you don't want to do it interactively, you can also just say 'set exposure to 37.' ")
        if (len(context.operations) == 0):
            raise IRError("Hmm, there's nothing to undo. ",
                          prompt="Try changing a slider, or applying an algorithm first. ",
                          say_metric_help=True)

        op = context.operations.pop()
        last_opname = OPNAME_TO_FRIENDLY_MAP.get(op.op, op.op)
        speak_output = f'OK, reverting the last change, which was {last_opname}. '
        prompt_output = "You can keep undoing, or now do some other operatioTry changing a metric, or applying an algorithm first.n such as setting exposure, or running H.D.R. "
        if (len(context.operations) == 0):
            prompt_output = "We're back to the un-edited version, so try editing a slider or running an algorithm. "
        new_url = context.build_image_url()
        card = StandardCard(
            title = f'Updated Photo {context.image_id}',
            text = f'Undid change: {op.op}',
            image = Image(large_image_url=new_url)
        )

        return (
            handler_input.response_builder
               .speak(speak_output)
               .set_card(card)
               .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
               .response
        )

class SaveImageIntentHandler(IRRequestHandler):
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_intent_name("SaveImageIntent")(handler_input)

    def handle_inner(self, handler_input, context):
        speak_output = ""
        prompt_output = ""
        card = None

        if context.in_interactive_edit:
            speak_output = f"OK, committing changes to {context.interactive_edit_metric}. Setting it to {context.interactive_edit_last_val}"
            prompt_output = "You're leaving interactive slider adjustment. Now you can set any slider value, interactively edit another one, or run an algorithm. "
            context.exit_interactive_mode('confirm')
            new_url = context.build_image_url()
            card = StandardCard(
                title = f'Updated Photo {context.image_id}',
                text = f'Done with interactive editing',
                image = Image(large_image_url=new_url)
            )
        elif context.image_url is not None:
            raise IRError(f"I don't yet support saving images to a device or database. Sorry about that. That said, I'm glad you are satisfied with your edited image! ",
                          prompt="You could always try editing another image. Or, if you're done, just say 'exit' or 'stop.' ")

        handler_input.response_builder.speak(speak_output)
        handler_input.response_builder.ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
        if card is not None:
            handler_input.response_builder.set_card(card)
        return handler_input.response_builder.response


class RaiseSliderInteractivelyIntentHandler(IRRequestHandler):
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_intent_name("RaiseSliderInteractivelyIntent")(handler_input)

    def handle_inner(self, handler_input, context):
        if not context.in_interactive_edit:
            raise IRError("Sorry, I can't do that yet. ",
                          prompt="Try saying either 'edit metric' or 'set metric to x.' The former starts an interactive editor where you can raise or lower, and the latter just assigns the metric a new value. ")
            # return SetSliderMetricIntentHandler.set_slider_metric(handler_input, context)

        adjust_amount = 0
        if context.interactive_edit_last_adjustment_dir == 'up':
            adjust_amount = context.interactive_edit_last_adjustment
        elif context.interactive_edit_last_adjustment_dir == 'down':
            adjust_amount = context.interactive_edit_last_adjustment // 2
        elif context.interactive_edit_last_adjustment_dir == 'none':
            adjust_amount = 50

        context.interactive_edit_last_val += adjust_amount
        context.interactive_edit_last_adjustment_dir = 'up'
        context.interactive_edit_last_adjustment = adjust_amount

        speak_output = f'OK, raising {context.interactive_edit_metric} by {adjust_amount}. '

        if context.interactive_edit_last_val >= 100:
            context.interactive_edit_last_val = 100
            speak_output += "This is as high as it can go. "

        if adjust_amount < 10 and not context.interactive_edit_fine_tuning_prompt_done:
            speak_output += f"Looks like we're dialing it in. {END_INTERACTIVE_HELP}"
            context.interactive_edit_fine_tuning_prompt_done = True

        prompt_output = f"How's it look? "
        card = context.build_interactive_card()

        return (
            handler_input.response_builder
               .speak(speak_output)
               .set_card(card)
               .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
               .response
        )


class LowerSliderInteractivelyIntentHandler(IRRequestHandler):
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_intent_name("LowerSliderInteractivelyIntent")(handler_input)

    def handle_inner(self, handler_input, context):
        if not context.in_interactive_edit:
            raise IRError("Sorry, I can't do that yet. ",
                          prompt="Try saying either 'edit metric' or 'set metric to x.' The former starts an interactive editor where you can raise or lower, and the latter just assigns the metric a new value. ")
            # return SetSliderMetricIntentHandler.set_slider_metric(handler_input, context)

        adjust_amount = 0
        if context.interactive_edit_last_adjustment_dir == 'down':
            adjust_amount = context.interactive_edit_last_adjustment
        elif context.interactive_edit_last_adjustment_dir == 'up':
            adjust_amount = context.interactive_edit_last_adjustment // 2
        elif context.interactive_edit_last_adjustment_dir == 'none':
            adjust_amount = 50

        context.interactive_edit_last_val -= adjust_amount
        context.interactive_edit_last_adjustment_dir = 'down'
        context.interactive_edit_last_adjustment = adjust_amount

        speak_output = f'OK, lowering {context.interactive_edit_metric} by {adjust_amount}. '

        if context.interactive_edit_last_val <= -100:
            context.interactive_edit_last_val = -100
            speak_output += "This is as low as it can go. "

        if adjust_amount < 10 and not context.interactive_edit_fine_tuning_prompt_done:
            speak_output += f"Looks like we're dialing it in. {END_INTERACTIVE_HELP}"
            context.interactive_edit_fine_tuning_prompt_done = True

        prompt_output = f"How's it look? "
        card = context.build_interactive_card()

        return (
            handler_input.response_builder
               .speak(speak_output)
               .set_card(card)
               .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
               .response
        )


class CompareImageIntentHandler(IRRequestHandler):
    def can_handle_inner(self, handler_input, context):
        return (
            ask_utils.is_intent_name("CompareImageIntent")(handler_input)
        )

    def handle_inner(self, handler_input, context):
        new_url = context.build_image_url(comparison=True)
        card = StandardCard(
            title = f'Side-by-side comparison',
            text = f'L: Original.\nR: Edited',
            image = Image(large_image_url=new_url)
        )

        speak_output = "OK, here's a comparison of your edits with the original image. "
        prompt_output = "What do you think? "

        return (
            handler_input.response_builder
               .speak(speak_output)
               .set_card(card)
               .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
               .response
        )

class HelpIntentHandler(IRRequestHandler):
    """Handler for Help Intent."""
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle_inner(self, handler_input, context:SessionContext):
        speak_output = "Image Retoucher is an interactive photo editing skill. "
        if context.image_url is None:
            speak_output += "You can load a photo to edit by saying 'edit image 0.' "
        else:
            speak_output = "You have an image to edit, so try adjusting exposure, contrast, saturation, or tint. You can also apply a number of algorithms to the image. Those algorithms are: histogram equalization, color transfer, sharpen filter, H.D.R., summer filter, winter filter, and sharpen filter.  "
        if context.in_interactive_edit:
            speak_output = "You're editing a slider right now. Try saying 'higher' or 'lower' depending on how you want to change it. I'll adjust the value by a bit less each time, so we can dial it in. When you're satisfied, say 'commit changes.' If you want to stop, just say 'cancel.' "
        
        if len(context.operations) > 2:
            speak_output += "By the way, you've made a lot of changes to this image. You can try saying 'compare to original' to see it right next to the un-edited version."

        prompt_output = "So... what would you like to do? "
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
                .response
        )


class CancelOrStopIntentHandler(IRRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle_inner(self, handler_input, context):
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle_inner(self, handler_input, context):
        speak_output = "Goodbye!"
        prompt_output = ""
        if context.in_interactive_edit:
            context.exit_interactive_mode('cancel')
            speak_output = 'OK, canceling the interactive edit session.'
            prompt_output = 'What would you like to do next?'
            new_url = context.build_image_url(comparison=True)
            card = StandardCard(
                title = f'Image {context.image_id}',
                image = Image(large_image_url=new_url)
            )


        if card is not None:
            handler_input.response_builder.set_card(card)
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
                .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle_inner(self, handler_input, context):
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return (
            handler_input.response_builder
                .speak("Hope you enjoyed using this app!")
        )


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
        speak_output = f"You just triggered {intent_name}, but right now I don't know how to handle that. "
        prompt_output = f"What would you like to do? "

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
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
            speak_output, prompt_output, card = exception.get_outputs()
        else:
            speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        handler_input.response_builder.speak(speak_output)
        handler_input.response_builder.ask(prompt_output, play_behavior = PlayBehavior.ENQUEUE)
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
sb.add_request_handler(LowerSliderInteractivelyIntentHandler())
sb.add_request_handler(RaiseSliderInteractivelyIntentHandler())
sb.add_request_handler(SetSliderMetricIntentHandler())
sb.add_request_handler(ApplyAlgorithmIntentHandler())
sb.add_request_handler(UndoChangesIntentHandler())
sb.add_request_handler(CompareImageIntentHandler())
sb.add_request_handler(SaveImageIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()