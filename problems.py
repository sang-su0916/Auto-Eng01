"""
English writing practice problems for the app.
"""

SAMPLE_PROBLEMS = {
    # 개인 및 일상생활 카테고리
    "개인/일상생활/자기소개": {
        "category": "개인/일상생활",
        "question": "Introduce yourself briefly and describe your hobbies and interests.",
        "context": "This is a self-introduction that might be used in a class, interview, or social setting.",
        "example": "Hello, my name is Min-su. I am a college student in Seoul. I like playing soccer and watching movies on weekends."
    },
    "개인/일상생활/일상 루틴": {
        "category": "개인/일상생활",
        "question": "Describe your daily routine on a typical weekday.",
        "context": "You are explaining your daily schedule to someone who wants to know about your lifestyle.",
        "example": "I usually wake up at 7 AM and eat breakfast before heading to work. After work, I go to the gym for an hour and then have dinner at home. I usually read a book or watch TV before going to bed around 11 PM."
    },
    
    # 여행 및 문화 카테고리
    "여행/문화/여행 경험": {
        "category": "여행/문화",
        "question": "Describe a memorable trip or travel experience you've had.",
        "context": "You are writing about a travel experience for a blog or sharing with friends.",
        "example": "Last summer, I visited Jeju Island with my family. It was an amazing experience. The beaches were beautiful and the food was delicious."
    },
    "여행/문화/한국 문화 소개": {
        "category": "여행/문화",
        "question": "Introduce an aspect of Korean culture to a foreign friend.",
        "context": "You are writing an email to a friend from another country who wants to learn about Korean culture.",
        "example": "One important aspect of Korean culture is respect for elders. In Korea, we use different language forms when speaking to older people, and we bow to show respect. Family gatherings, especially during holidays like Chuseok and Seollal, are very important in maintaining these traditions."
    },
    
    # 학업 및 교육 카테고리
    "교육/학업/미래 계획": {
        "category": "교육/학업",
        "question": "What are your plans for the future? Describe your career goals and aspirations.",
        "context": "You're writing about your future plans, perhaps for a job application or university admission.",
        "example": "In the future, I want to become a software engineer. I am studying computer science and practicing coding every day to achieve my goal."
    },
    "교육/학업/학교생활": {
        "category": "교육/학업",
        "question": "Describe your school or university life and what you enjoy about it.",
        "context": "You are writing about your educational experience for a school newspaper or blog.",
        "example": "I'm currently in my second year at Seoul National University, studying Business Administration. I enjoy attending lectures, especially those about marketing strategies. I'm also a member of the debate club, which helps me improve my critical thinking skills."
    },
    
    # 사회적 이슈 카테고리
    "사회/이슈/환경 문제": {
        "category": "사회/이슈",
        "question": "What do you think is the most serious environmental problem today, and how can we solve it?",
        "context": "You are writing an opinion piece for a class assignment or online forum.",
        "example": "I believe climate change is the most serious environmental problem we face today. To solve this issue, we need to reduce carbon emissions by using renewable energy sources like solar and wind power. Individuals can also help by using public transportation, reducing waste, and conserving energy at home."
    },
    "사회/이슈/기술 발전": {
        "category": "사회/이슈",
        "question": "How has technology changed our daily lives, and is this change positive or negative?",
        "context": "You are writing an essay discussing the impact of technology on society.",
        "example": "Technology has dramatically changed our daily lives in many ways. Smartphones allow us to communicate instantly and access information anytime. While this connectivity has made life more convenient, it has also created problems like digital addiction and privacy concerns. Overall, I think technology has brought more benefits than drawbacks, but we need to use it wisely."
    },
    
    # 엔터테인먼트 카테고리
    "엔터테인먼트/영화 리뷰": {
        "category": "엔터테인먼트",
        "question": "Write a review of a movie you've recently watched.",
        "context": "You are writing a movie review for a blog or social media post.",
        "example": "I recently watched 'Parasite' directed by Bong Joon-ho. It's a brilliant film that explores social inequality in Korea through a captivating story. The acting was exceptional, especially by Song Kang-ho. The plot had many unexpected twists that kept me engaged throughout. I highly recommend this movie to anyone who enjoys thought-provoking films."
    },
    "엔터테인먼트/좋아하는 책": {
        "category": "엔터테인먼트",
        "question": "Describe your favorite book and why you enjoy it.",
        "context": "You are sharing your literary preferences with a book club or online community.",
        "example": "My favorite book is 'To Kill a Mockingbird' by Harper Lee. I love this novel because it addresses important themes like racial injustice and moral growth through the perspective of a young girl. The characters are well-developed, especially Atticus Finch, who demonstrates courage and integrity in difficult circumstances. The book taught me valuable lessons about empathy and standing up for what is right."
    },
    
    # 비즈니스 및 업무 카테고리
    "비즈니스/업무/이메일 작성": {
        "category": "비즈니스/업무",
        "question": "Write a formal email to a potential business partner suggesting a meeting.",
        "context": "You are a marketing manager initiating contact with a company you'd like to collaborate with.",
        "example": "Dear Mr. Johnson,\n\nI am writing on behalf of ABC Company to express our interest in collaborating with your organization on the upcoming marketing campaign. Our companies share similar values and target audiences, which I believe creates a great opportunity for partnership.\n\nI would like to suggest a meeting next week to discuss potential collaboration opportunities. Would you be available on Tuesday at 2 PM?\n\nI look forward to your response.\n\nSincerely,\nJane Smith\nMarketing Manager\nABC Company"
    },
    "비즈니스/업무/회의 요약": {
        "category": "비즈니스/업무",
        "question": "Write a summary of a business meeting for your colleagues.",
        "context": "You attended an important meeting and need to share the key points with team members who couldn't attend.",
        "example": "Meeting Summary: Product Development Strategy\nDate: March 15, 2023\nParticipants: Marketing, R&D, and Sales teams\n\nKey Points Discussed:\n1. The launch date for the new product line is confirmed for September 2023.\n2. The marketing team presented the promotional campaign, which was approved with minor adjustments.\n3. Sales projections were reviewed and adjusted based on recent market research.\n\nAction Items:\n- Marketing: Finalize campaign materials by July 1\n- R&D: Complete product testing by August 15\n- Sales: Prepare training materials for the sales team by August 30\n\nThe next follow-up meeting is scheduled for April 20."
    },
    
    # 음식 및 요리 카테고리
    "음식/요리/한국 음식 소개": {
        "category": "음식/요리",
        "question": "Describe a traditional Korean dish and how it's prepared.",
        "context": "You are explaining Korean cuisine to someone from another country.",
        "example": "Kimchi is one of the most famous Korean dishes. It's made by fermenting cabbage with salt, garlic, ginger, and red pepper powder. The vegetables are first soaked in salt water, then mixed with the seasonings and stored in jars to ferment. Kimchi is not only delicious but also very healthy because it contains beneficial probiotics."
    },
    "음식/요리/요리 경험": {
        "category": "음식/요리",
        "question": "Describe your experience cooking a special meal.",
        "context": "You are sharing a cooking experience with friends or in a cooking blog.",
        "example": "Last weekend, I cooked a special dinner for my family. I prepared grilled salmon with lemon sauce, roasted vegetables, and chocolate cake for dessert. It was my first time making salmon, and I was nervous about overcooking it. Fortunately, everything turned out delicious, and my family was impressed. I learned that cooking requires patience and careful preparation."
    }
} 