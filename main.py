import discord
from openai import OpenAI
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

load_dotenv()
token=os.getenv("DISCORD_TOKEN")
openai_api_key=os.getenv('OPENAI_API_KEY')

handler=logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents=discord.Intents.default()
intents.message_content=True
intents.members=True

bot = commands.Bot(command_prefix='!', intents=intents)
openai=OpenAI()


class ContextBot:
    def __init__(self):
        self.message_cache = {}  # Channel ID -> list of recent messages
        self.cache_limit = 5    # Number of messages to keep in context
        
    async def add_message_to_cache(self, message):

        channel_id = message.channel.id
        
        if channel_id not in self.message_cache:
            self.message_cache[channel_id] = []
        
        # Add message info to cache
        msg_data = {
            'author': message.author.display_name,
            'content': message.content,
            'timestamp': message.created_at,
            'id': message.id
        }
        
        self.message_cache[channel_id].append(msg_data)
        
        # Keep only recent messages
        if len(self.message_cache[channel_id]) > self.cache_limit:
            self.message_cache[channel_id] = self.message_cache[channel_id][-self.cache_limit:]
    
    async def get_context(self, channel_id, current_message_id):

        if channel_id not in self.message_cache:
            return []
        
        # Get messages excluding the current mention
        context_messages = [
            msg for msg in self.message_cache[channel_id] 
            if msg['id'] != current_message_id
        ]
        
        # Return last 10 messages for context
        return context_messages[-10:]
    
    async def generate_response(self, question, context_messages, mentioned_user):

        # Build context string
        context_str = ""
        if context_messages:
            context_str = "Recent conversation:\n"
            for msg in context_messages:
                # Skip bot messages and commands
                if not msg['content'].startswith('!') and not msg['content'].startswith('<@'):
                    context_str += f"{msg['author']}: {msg['content']}\n"
        
        # Create prompt for Claude
        system_prompt = f"""You are a helpful Discord bot called tanyafinwiz, and you specialize in giving answer regarding financial topics. 
        Your task is to provide helpful responses based on the conversation context, in the spirit of improving financial literacy and understanding. 
        You should:
        - Provide accurate, concise answers to questions about financial topics.
        - Use the context of the conversation to inform your responses.
        - Avoid giving personal opinions or advice or speculation.
        - Give cautions about financial risks when appropriate.
        - Say "I don't know" if you are unsure about something.
        - Give references to financial concepts or resources when appropriate.
        - Refrain answering questions that are not related to financial topics.
        You've been mentioned in a conversation and need to respond."""
        
        user_prompt = f"""{context_str}.
        {mentioned_user} asked: {question}"""

        prompts=[{'role': 'system', 'content':system_prompt},
                 {'role':'user', 'content': user_prompt}]

        try:
            # Use Claude Haiku for faster responses (cheaper too)
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # or "claude-3-5-sonnet-20241022" for better quality
                max_tokens=150,
                messages=prompts,
                temperature=0.2)
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return "Sorry, I'm having trouble processing that right now. Please try again later!"

# Initialize context bot
context_bot = ContextBot()

@bot.event
async def on_ready():
    print(f'Ready when you are! {bot.user.name}')
    print('------')

@bot.event
async def on_member_join(member):
    await member.send(f'Welcome aboard, {member.mention}!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    await context_bot.add_message_to_cache(message)
    
    # Check if the bot is mentioned in the message
    if bot.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == bot.user):
        async with message.channel.typing():  # Show typing indicator
            try:
                # Get channel id and message id that triggered the mention
                context_messages = await context_bot.get_context(
                    message.channel.id, message.id
                )
                
                # Clean the question (remove mention)
                question = message.content
                for mention in message.mentions:
                    question = question.replace(f'<@{mention.id}>', '').strip()
                    question = question.replace(f'<@!{mention.id}>', '').strip()
                
                # Generate response
                response = await context_bot.generate_response(
                    question, 
                    context_messages, 
                    message.author.display_name
                )
                
                # Reply to the user
                await message.reply(response)
                
            except Exception as e:
                print(f"Error processing message: {e}")
                await message.reply("Sorry, I encountered an error processing your request!")
    
    # Process other commands
    await bot.process_commands(message)

@bot.command(name='clear_context')
async def clear_context(ctx):
    """Clear the conversation context for this channel"""
    channel_id = ctx.channel.id
    if channel_id in context_bot.message_cache:
        context_bot.message_cache[channel_id] = []
    await ctx.send("Context cleared for this channel!")

@bot.command()
async def hello (ctx):
    await ctx.send(f'Hello {ctx.author.mention}!')

@bot.command()
async def context_size(ctx):
    """Show how many messages are in context"""
    channel_id = ctx.channel.id
    size = len(context_bot.message_cache.get(channel_id, []))
    await ctx.send(f"I'm keeping track of {size} recent messages in this channel.")

# Run the bot
if __name__ == "__main__":
    # Make sure to set your environment variables:
    # DISCORD_BOT_TOKEN=your_discord_bot_token
    # ANTHROPIC_API_KEY=your_anthropic_api_key
    
    # discord_token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN environment variable not set!")
        exit(1)
    
    if not os.getenv('OPENAI_API_KEY'):
        print("Error: LLM API KEY not set!")
        exit(1)
    
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)


# bot.run(token, log_handler=handler, log_level=logging.DEBUG)

