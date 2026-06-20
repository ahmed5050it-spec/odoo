# Value Configuration Framework

This module implements the value configuration methodology from **Stabell & Fjeldstad (1998)**: *"Configuring Value for Competitive Advantage: On Chains, Shops, and Networks"*.

It also integrates with the **APQC Process Classification Framework (PCF)** v7.2.1 to provide a comprehensive process-to-value mapping system.

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

## PCF Framework Integration

The module integrates the **APQC Process Classification Framework (PCF)** - a cross-industry process taxonomy that provides standardized business process definitions.

### PCF Structure

The PCF organizes processes into **13 major categories**:

| Category | Name | Examples |
|----------|------|----------|
| 1.0 | Develop Vision and Strategy | Competitive analysis, customer needs assessment |
| 2.0 | Develop and Manage Products/Services | Product lifecycle, portfolio management |
| 3.0 | Market and Sell | Market intelligence, customer acquisition |
| 4.0 | Deliver Physical Products | Manufacturing, production planning |
| 5.0 | Deliver Services | Service delivery, governance |
| 6.0 | Manage Customer Service | Service strategy, warranty management |
| 7.0 | Develop and Manage Human Capital | HR strategy, workforce planning |
| 8.0 | Manage Information Technology | IT relationships, service management |
| 9.0 | Manage Financial Resources | Budgeting, cost accounting |
| 10.0 | Acquire, Construct, and Manage Assets | Property strategy, facility management |
| 11.0 | Manage Enterprise Risk & Compliance | Risk framework, compliance |
| 12.0 | Manage External Relationships | Investor relations, government relations |
| 13.0 | Develop and Manage Business Capabilities | Process management, governance |

Each category contains 2-3 nested levels of detailed processes.

### Mapping PCF to Value Configurations

**How to map PCF processes to your value configuration:**

1. **Import PCF Framework**
   - Go to **Tools → Value Configuration → PCF Framework → Import PCF Framework**
   - Click **Import PCF Framework** to load all 13 categories and 50+ processes

2. **Create Mappings**
   - Open your **Value Configuration**
   - Click the **PCF Mappings** tab
   - Set **PCF Version** (e.g., 7.2.1)
   - Set **PCF Adoption Level** (Partial or Full)

3. **Map Processes to Activities**
   - Click **Create** to add a mapping
   - Select a PCF Process and Value Activity
   - Set **Relevance Level**: 
     - Primary: Core to the activity
     - Secondary: Supports the activity
     - Tertiary: Occasional reference
   - Enter **Process Percentage** (effort allocation)
   - Document applicable industries

4. **Define KPIs**
   - For each mapping, add Key Performance Indicators
   - Track Cost, Quality, Time, Effectiveness, Efficiency KPIs
   - Set current and target values
   - Compare to industry benchmarks

### Example: Manufacturing Value Chain + PCF

```
Value Configuration: Manufacturing Operations

Value Activity: Operations
├─ PCF 4.1.1 (Primary, 70%) - Develop production and materials strategies
├─ PCF 4.1.2 (Primary, 20%) - Manage demand for products
└─ PCF 8.0 (Secondary, 10%) - Manage Information Technology

KPIs:
├─ Production Cost per Unit (Target: $50)
├─ On-time Delivery Rate (Target: 98%)
├─ Machine Utilization (Target: 85%)
└─ Defect Rate (Target: <0.5%)
```

### Example: Professional Services Value Shop + PCF

```
Value Configuration: Management Consulting

Value Activity: Problem-solving
├─ PCF 2.0 (Primary, 40%) - Develop and Manage Products and Services
├─ PCF 3.1 (Secondary, 30%) - Understand markets and customers
└─ PCF 13.1 (Secondary, 30%) - Manage business processes

Value Drivers:
├─ Reputation (tracked via PCF 3.0 metrics)
├─ Solution Quality (measured by client satisfaction)
└─ Expertise (tracked via team credentials in PCF 7.0)
```

### PCF Data Models

The module includes:

- **PCFCategory** - 13 major process categories (1.0-13.0)
- **PCFProcess** - 50+ detailed processes with hierarchy
- **PCFActivityMapping** - Links processes to value activities
- **PCFActivityKPI** - Performance metrics for each mapping

### Benefits of PCF Integration

✅ **Standardized Process Language** - Industry-standard process definitions  
✅ **Benchmarking** - Compare against industry practices  
✅ **Comprehensive Coverage** - All business processes covered  
✅ **Scalability** - From small teams to enterprise  
✅ **Cross-Industry** - Applicable to any industry  
✅ **Change Tracking** - Monitor PCF version changes  

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

### Core Value Configuration Models

1. **value.configuration** - Main value configuration records
   - Configuration type (chain/shop/network)
   - Activities and drivers
   - PCF mappings
   
2. **value.activity** - Primary and support activities
   - Performance metrics
   - Dependencies and relationships
   - Cost and value impact
   
3. **value.driver** - Cost and value drivers
   - Performance tracking (current vs. target)
   - Strategic importance
   - Optimization strategy

### PCF Integration Models

4. **pcf.category** - APQC PCF main categories (1.0-13.0)
   - Hierarchy support for nested categories
   - Metrics availability tracking
   - Version change documentation
   
5. **pcf.process** - Detailed PCF processes
   - Full process hierarchy (up to 4 levels deep)
   - Process identifiers and codes
   - Metrics availability
   - Change tracking from previous versions
   
6. **pcf.activity.mapping** - Process-to-Activity relationships
   - Links PCF processes to value activities
   - Relevance level (primary/secondary/tertiary)
   - Process effort allocation
   - Industry applicability
   
7. **pcf.activity.kpi** - Performance metrics
   - Cost, quality, time, effectiveness, efficiency KPIs
   - Current and target performance
   - Industry benchmarks
   - Source tracking (PCF/organizational/industry)
