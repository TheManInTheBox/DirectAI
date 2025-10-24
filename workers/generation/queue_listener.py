"""
Service Bus Queue Listener for Generation Worker
Polls the generation-jobs queue and processes generation requests
"""
import os
import json
import logging
import asyncio
from typing import Optional

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)


class GenerationQueueListener:
    """
    Service Bus queue listener that polls for generation job messages
    and triggers the generation processing workflow
    """
    
    def __init__(self, process_generation_callback):
        """
        Initialize the queue listener
        
        Args:
            process_generation_callback: Async function to call when a job is received
                                        Should accept (generation_request_id, audio_file_id, parameters, callback_url)
        """
        self.process_generation_callback = process_generation_callback
        
        # Get Service Bus configuration from environment
        # Support both formats: SERVICE_BUS_NAMESPACE (with .servicebus.windows.net) and SERVICEBUS_NAMESPACE (just namespace)
        service_bus_namespace_full = os.getenv("SERVICE_BUS_NAMESPACE")  # e.g., "namespace.servicebus.windows.net"
        servicebus_namespace = os.getenv("SERVICEBUS_NAMESPACE")  # e.g., "namespace"
        
        if service_bus_namespace_full:
            # Remove .servicebus.windows.net suffix if present
            self.servicebus_namespace = service_bus_namespace_full.replace('.servicebus.windows.net', '')
        elif servicebus_namespace:
            self.servicebus_namespace = servicebus_namespace
        else:
            self.servicebus_namespace = None
        
        self.queue_name = os.getenv("GENERATION_QUEUE_NAME") or os.getenv("SERVICEBUS_QUEUE_NAME", "generation-jobs")
        self.use_managed_identity = os.getenv("SERVICEBUS_USE_MANAGED_IDENTITY", "true").lower() == "true"
        self.connection_string = os.getenv("SERVICEBUS_CONNECTION_STRING")
        
        self.client: Optional[ServiceBusClient] = None
        self.is_running = False
        
        logger.info(f"Queue listener initialized for queue: {self.queue_name}")
        logger.info(f"Using managed identity: {self.use_managed_identity}")
        logger.info(f"Namespace: {self.servicebus_namespace}")
    
    async def start(self):
        """Start the queue listener"""
        if self.is_running:
            logger.warning("Queue listener is already running")
            return
        
        try:
            # Create Service Bus client
            if self.use_managed_identity:
                if not self.servicebus_namespace:
                    raise ValueError("SERVICEBUS_NAMESPACE environment variable is required for managed identity")
                
                credential = DefaultAzureCredential()
                fully_qualified_namespace = f"{self.servicebus_namespace}.servicebus.windows.net"
                self.client = ServiceBusClient(
                    fully_qualified_namespace=fully_qualified_namespace,
                    credential=credential,
                    logging_enable=True
                )
                logger.info(f"Connected to Service Bus using managed identity: {fully_qualified_namespace}")
            else:
                if not self.connection_string:
                    raise ValueError("SERVICEBUS_CONNECTION_STRING environment variable is required")
                
                self.client = ServiceBusClient.from_connection_string(
                    conn_str=self.connection_string,
                    logging_enable=True
                )
                logger.info("Connected to Service Bus using connection string")
            
            self.is_running = True
            
            # Start listening loop
            await self._listen_loop()
            
        except Exception as e:
            logger.error(f"Error starting queue listener: {str(e)}", exc_info=True)
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop the queue listener"""
        logger.info("Stopping queue listener...")
        self.is_running = False
        
        if self.client:
            await self.client.close()
            self.client = None
        
        logger.info("Queue listener stopped")
    
    async def _listen_loop(self):
        """Main listening loop that polls for messages"""
        logger.info(f"Starting to listen for messages on queue: {self.queue_name}")
        
        async with self.client:
            receiver = self.client.get_queue_receiver(
                queue_name=self.queue_name,
                max_wait_time=30  # Wait up to 30 seconds for new messages
            )
            
            async with receiver:
                while self.is_running:
                    try:
                        # Receive messages in batches
                        messages = await receiver.receive_messages(
                            max_message_count=1,
                            max_wait_time=30
                        )
                        
                        for message in messages:
                            try:
                                await self._process_message(message, receiver)
                            except Exception as process_error:
                                logger.error(f"Error processing message: {str(process_error)}", exc_info=True)
                                # Don't complete the message - it will be retried
                                await receiver.abandon_message(message)
                        
                        # Small delay between polling cycles
                        if not messages:
                            await asyncio.sleep(1)
                    
                    except Exception as e:
                        logger.error(f"Error in listen loop: {str(e)}", exc_info=True)
                        await asyncio.sleep(5)  # Back off on errors
    
    async def _process_message(self, message, receiver):
        """
        Process a single Service Bus message
        
        Message format (JSON):
        {
            "generation_request_id": "guid",
            "audio_file_id": "guid" (optional),
            "parameters": {
                "target_bpm": 120.0,
                "duration_seconds": 30.0,
                "style": "rock",
                ...
            },
            "callback_url": "http://..." (optional)
        }
        """
        try:
            # Parse message body
            message_body = str(message)
            logger.info(f"Received message: {message_body[:200]}...")  # Log first 200 chars
            
            data = json.loads(message_body)
            
            generation_request_id = data.get("generation_request_id")
            audio_file_id = data.get("audio_file_id")
            parameters = data.get("parameters", {})
            callback_url = data.get("callback_url")
            
            if not generation_request_id:
                raise ValueError("Missing generation_request_id in message")
            
            logger.info(f"Processing generation request: {generation_request_id}")
            
            # Call the generation processing callback
            await self.process_generation_callback(
                generation_request_id=generation_request_id,
                audio_file_id=audio_file_id,
                parameters=parameters,
                callback_url=callback_url
            )
            
            # Message processed successfully - complete it
            await receiver.complete_message(message)
            logger.info(f"Message completed for generation request: {generation_request_id}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {str(e)}")
            # Dead letter the message - it's malformed
            await receiver.dead_letter_message(
                message,
                reason="InvalidJSON",
                error_description=str(e)
            )
        
        except ValueError as e:
            logger.error(f"Invalid message format: {str(e)}")
            # Dead letter the message - missing required fields
            await receiver.dead_letter_message(
                message,
                reason="InvalidFormat",
                error_description=str(e)
            )
        
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            # Don't complete - let it retry
            raise
