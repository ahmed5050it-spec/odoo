# Value Configuration Framework

This module implements the value configuration methodology from **Stabell & Fjeldstad (1998)**: *"Configuring Value for Competitive Advantage: On Chains, Shops, and Networks"*.

## Overview

The module provides tools to configure and analyze your business's value creation logic across three generic value configuration models:

### 1. **Value Chain** (Long-linked Technology)
- **Logic**: Transform inputs into products sequentially
- **Activities**: Inbound Logistics → Operations → Outbound Logistics → Marketing & Sales → Service
- **Key Drivers**: Scale, Capacity Utilization
- **Best For**: Manufacturing, Product-based businesses
- **Examples**: Copier manufacturers, automotive

### 2. **Value Shop** (Intensive Technology)
- **Logic**: Resolve unique customer problems cyclically
- **Activities**: Problem-finding → Problem-solving → Choice → Execution → Control & Evaluation
- **Key Drivers**: Reputation, Scale (signals value)
- **Best For**: Professional services, consulting, engineering
- **Examples**: Medical practices, law firms, engineering firms, R&D departments

### 3. **Value Network** (Mediating Technology)
- **Logic**: Link customers and facilitate exchanges through parallel activities
- **Activities**: Network Promotion & Contract Management → Service Provisioning → Infrastructure Operation
- **Key Drivers**: Scale (network externalities), Capacity Utilization
- **Best For**: Telecommunications, banking, insurance, transportation
- **Examples**: Telephone companies, retail banks, insurance companies

## How to Configure Values in Odoo

### Step 1: Create a Value Configuration

1. Go to **Tools → Value Configuration**
2. Click **Create**
3. Enter a name (e.g., "Manufacturing Value Chain")
4. Select the configuration type:
   - **Value Chain** for sequential, transformation-focused businesses
   - **Value Shop** for problem-solving, cyclical businesses
   - **Value Network** for mediating, network-based businesses

### Step 2: Review Auto-Generated Activities

The system automatically creates primary activities based on your configuration type:

- **For Value Chain**: Inbound Logistics, Operations, Outbound Logistics, Marketing & Sales, Service
- **For Value Shop**: Problem-finding & Acquisition, Problem-solving, Choice, Execution, Control & Evaluation
- **For Value Network**: Network Promotion & Contract Management, Service Provisioning, Infrastructure Operation

**To customize activities:**
1. Click the **Activities** tab
2. Edit activity details:
   - Mark critical competencies with **Is Core Competency**
   - Set **Cost Percentage** to estimate activity cost allocation
   - Indicate **Value Impact** (Low/Medium/High)
   - Add **Performance Metric** to track activity efficiency

### Step 3: Configure Cost Drivers

Cost drivers are structural factors that determine activity costs.

**Cost drivers automatically created:**
- Scale: Economies of scale and efficiency
- Capacity Utilization: Optimization of resource utilization

**To optimize cost drivers:**
1. Click the **Cost Drivers** tab
2. For each driver:
   - Set **Current Performance** (current metric value)
   - Set **Target Performance** (desired level)
   - Write **Optimization Strategy** (how to improve)
   - Mark **Impact Level** (Low/Medium/High/Critical)
   - Link **Related Activities** most affected by this driver

### Step 4: Configure Value Drivers

Value drivers are factors that create value for customers. These vary by configuration type:

- **Value Chain**: Focus is on cost leadership (fewer explicit value drivers)
- **Value Shop**: **Reputation** is the canonical value driver
  - Success in problem-solving builds reputation
  - Reputation attracts better talent and better clients
- **Value Network**: **Scale** and **Capacity Utilization** drive value
  - More customers = more value for existing customers (positive network externalities)
  - Reliability and availability create value through good service

**To configure value drivers:**
1. Click the **Value Drivers** tab
2. Add new drivers or edit existing ones:
   - Describe the driver
   - Set impact level
   - Document how it creates competitive advantage
   - Link related activities
   - Track performance metrics

### Step 5: Analyze Competitive Position

Use the configured framework to:

1. **Identify strategic advantages**: Which cost/value drivers do you excel at?
2. **Find improvement opportunities**: Where is performance below target?
3. **Understand activity interdependencies**: How do activities depend on each other?
4. **Benchmark against competitors**: Compare your driver performance with industry standards

## Key Metrics to Track

### Value Chain
- **Cost per unit**: Track cost drivers' impact on unit economics
- **Capacity utilization**: Monitor how well you use production capacity
- **Scale efficiency**: Measure cost reductions from increasing scale

### Value Shop
- **Reputation indicators**: Awards, certifications, client testimonials
- **Problem-solving success rate**: % of problems solved satisfactorily
- **Client retention**: Repeat business and referral rates
- **Team quality**: Qualifications and experience of professionals

### Value Network
- **Network size**: Total number of customers/members
- **Network composition**: Balance of different customer types
- **Service availability**: Uptime and accessibility metrics
- **Customer switching costs**: Strength of network lock-in

## Strategic Positioning Options

### Value Chain
- **Vertical integration**: Control supply chain and distribution
- **Scale vs. Specialization**: Build large volumes vs. focus on segments
- **Cost vs. Differentiation**: Compete on cost leadership vs. product features

### Value Shop
- **Specialization scope**: Broad generalist vs. narrow specialist
- **Problem incorporation**: Bring clients/objects to your facility vs. work on-site
- **Vertical integration**: Partner with specialists vs. in-house capabilities

### Value Network
- **Vertical scope**: Control all mediation levels vs. partner with others
- **Horizontal scope**: Serve specific customer segments vs. broad market
- **Network membership**: Selective (quality) vs. open (quantity)

## Implementation Example: Professional Services Firm (Value Shop)

```
Configuration Name: Professional Consulting Services

Configuration Type: Value Shop (Intensive)

Activities:
1. Problem-finding & Acquisition
   - Core Competency: Yes
   - Value Impact: High
   - Metric: Sales pipeline size
   
2. Problem-solving
   - Cost Percentage: 45%
   - Value Impact: High
   - Metric: Solution quality score
   
3. Choice
   - Value Impact: Medium
   - Metric: Decision time
   
4. Execution
   - Cost Percentage: 30%
   - Value Impact: High
   - Metric: On-time delivery %
   
5. Control & Evaluation
   - Cost Percentage: 15%
   - Value Impact: High
   - Metric: Client satisfaction score

Cost Drivers:
- Scale: Current 15 consultants → Target 25 (leverage senior staff)
- Capacity Utilization: Current 70% → Target 85%

Value Drivers:
- Reputation: Current score 7/10 → Target 9/10 (industry awards)
- Quality: Client satisfaction target 95%
```

## Reports and Analysis

Use the configuration data for:

1. **Organizational Design**: Align structure with value configuration type
2. **Strategic Planning**: Identify which drivers to invest in
3. **Performance Management**: Track metrics for each activity and driver
4. **Competitive Analysis**: Compare your configuration with competitors
5. **M&A Analysis**: Understand target company's value configuration

## References

- **Stabell, C. B., & Fjeldstad, Ø. D. (1998).** Configuring value for competitive advantage: On chains, shops, and networks. *Strategic Management Journal, 19*(5), 413-437.

- **Thompson, J. D. (1967).** Organizations in Action. McGraw-Hill.

- **Porter, M. E. (1985).** Competitive Advantage: Creating and Sustaining Superior Performance. Free Press.

## Module Information

- **Name**: Value Configuration Framework
- **Version**: 1.0.0
- **Category**: Tools
- **License**: LGPL-3
- **Dependencies**: base

## Models

1. **value.configuration** - Main value configuration records
2. **value.activity** - Primary and support activities
3. **value.driver** - Cost and value drivers
