"""
Service Bus Queue Listener for Training Jobs
Listens to training-jobs queue and processes training requests
"""
import os
import json
import logging
import asyncio
from typing import Callable, Optional
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)


class TrainingQueueListener:
    """
    Listens to Azure Service Bus queue for training job messages
    """
    
    def __init__(self, training_service):
        """
        Initialize the queue listener
        
        Args:
            training_service: MusicGenTrainingService instance
        """
        self.training_service = training_service
        
        # Service Bus configuration
        self.servicebus_namespace = os.getenv("SERVICE_BUS_NAMESPACE")
        self.queue_name = os.getenv("TRAINING_QUEUE_NAME", "training-jobs")
        
        # State
        self.client: Optional[ServiceBusClient] = None
        self.is_running = False
        
        logger.info(f"TrainingQueueListener initialized for namespace: {self.servicebus_namespace}")
    
    async def start(self):
        """Start listening to the queue"""
        if not self.servicebus_namespace:
            logger.warning("SERVICE_BUS_NAMESPACE not configured. Queue listener disabled.")
            return
        
        try:
            self.is_running = True
            
            # Use managed identity for authentication
            credential = DefaultAzureCredential()
            
            self.client = ServiceBusClient(
                fully_qualified_namespace=f"{self.servicebus_namespace}.servicebus.windows.net",
                credential=credential
            )
            
            logger.info(f"Connected to Service Bus using managed identity: {self.servicebus_namespace}.servicebus.windows.net")
            
            # Start listening loop
            await self._listen_loop()
            
        except Exception as e:
            logger.error(f"Error starting queue listener: {str(e)}", exc_info=True)
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop listening to the queue"""
        self.is_running = False
        if self.client:
            await self.client.close()
            logger.info("Service Bus client closed")
    
    async def _listen_loop(self):
        """Main loop for listening to messages"""
        logger.info(f"Starting to listen for messages on queue: {self.queue_name}")
        
        async with self.client:
            receiver = self.client.get_queue_receiver(
                queue_name=self.queue_name,
                max_wait_time=30  # Wait up to 30 seconds for messages
            )
            
            async with receiver:
                while self.is_running:
                    try:
                        # Receive messages
                        received_msgs = await receiver.receive_messages(
                            max_message_count=1,
                            max_wait_time=30
                        )
                        
                        for message in received_msgs:
                            try:
                                await self._process_message(message, receiver)
                                # Complete the message (remove from queue)
                                await receiver.complete_message(message)
                                logger.info(f"Message completed successfully")
                                
                            except Exception as e:
                                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                                # Dead-letter the message if processing fails
                                await receiver.dead_letter_message(
                                    message,
                                    reason="ProcessingError",
                                    error_description=str(e)
                                )
                                logger.warning(f"Message moved to dead-letter queue")
                        
                        # Small delay to prevent tight loop
                        if not received_msgs:
                            await asyncio.sleep(1)
                            
                    except asyncio.CancelledError:
                        logger.info("Listen loop cancelled")
                        break
                    except Exception as e:
                        logger.error(f"Error in listen loop: {str(e)}", exc_info=True)
                        await asyncio.sleep(5)  # Wait before retrying
    
    async def _process_message(self, message, receiver):
        """
        Process a single training job message
        
        Message format:
        {
            "job_id": "uuid",
            "dataset_id": "uuid",
            "model_name": "my-custom-model",
            "base_model": "facebook/musicgen-melody-large",
            "epochs": 100,
            "learning_rate": 0.0001,
            "lora_rank": 8,
            "lora_alpha": 16,
            "batch_size": 1,
            "callback_url": "https://api.../training/callback"
        }
        """
        try:
            # Parse message body
            message_body = str(message)
            logger.info(f"Received message: {message_body[:200]}...")
            
            data = json.loads(message_body)
            
            # Validate required fields
            required_fields = ["job_id", "dataset_id", "model_name"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Extract training parameters
            job_id = data["job_id"]
            dataset_id = data["dataset_id"]
            model_name = data["model_name"]
            
            logger.info(f"Processing training job {job_id} for dataset {dataset_id}")
            
            # Start training
            result = await self.training_service.train_model(
                dataset_id=dataset_id,
                model_name=model_name,
                epochs=data.get("epochs", 100),
                learning_rate=data.get("learning_rate", 1e-4),
                lora_rank=data.get("lora_rank", 8),
                lora_alpha=data.get("lora_alpha", 16),
                batch_size=data.get("batch_size", 1)
            )
            
            logger.info(f"Training completed successfully for job {job_id}")
            logger.info(f"Result: {result}")
            
            # Send callback if URL provided
            if "callback_url" in data:
                await self._send_callback(
                    callback_url=data["callback_url"],
                    job_id=job_id,
                    status="completed",
                    result=result
                )
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {str(e)}")
            raise ValueError(f"Invalid message format: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing training job: {str(e)}", exc_info=True)
            raise
    
    async def _send_callback(self, callback_url: str, job_id: str, status: str, result: dict):
        """Send callback to API with training results"""
        try:
            import aiohttp
            
            payload = {
                "job_id": job_id,
                "status": status,
                "model_id": result.get("model_id"),
                "model_path": result.get("model_path"),
                "training_time": result.get("training_time"),
                "final_loss": result.get("final_loss")
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(callback_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Callback sent successfully for job {job_id}")
                    else:
                        logger.warning(f"Callback failed with status {response.status}")
                        
        except Exception as e:
            logger.error(f"Error sending callback: {str(e)}", exc_info=True)
            # Don't raise - callback failure shouldn't fail the job
